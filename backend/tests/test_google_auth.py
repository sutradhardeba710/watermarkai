"""Google Sign-In — server-side ID-token verification + google_login policy.

Pure unit tests (no network, no Postgres/Redis). The DB is an in-memory SQLite
session so the create/link/lookup paths run without external dependencies; the
Google token itself is faked by monkeypatching ``verify_google_id_token``.

Covers:
  - app.core.google_oauth.verify_google_id_token (disabled config, forged token,
    bad issuer, no email claim)
  - app.services.auth_service.google_login (new user, link-to-verified,
    block-link-to-unverified, returning user, suspended/deleted)
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from app.core import google_oauth
from app.core.errors import AppError
from app.core.google_oauth import GoogleProfile, verify_google_id_token
from app.core.security import hash_password
from app.models import AccountStatus, Base, User, UserRole
from app.schemas.auth import LoginRequest
from app.services import auth_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """In-memory SQLite session with the ORM schema created/dropped per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def _profile(sub: str = "google-sub-123", email: str = "user@example.com",
             email_verified: bool = True, full_name: str = "Jane Doe") -> GoogleProfile:
    return GoogleProfile(sub=sub, email=email, email_verified=email_verified, full_name=full_name)


@pytest.fixture(autouse=True)
def _enable_google(monkeypatch):
    """Force the OAuth client ID on so the disabled-config gate is off by default.
    Individual tests opt back out by clearing it on the cached settings object."""
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "test-client-id")


def _patch_verify(monkeypatch, profile: GoogleProfile):
    """Make auth_service accept any credential and resolve to ``profile``."""
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda _cred: profile)


# ---------------------------------------------------------------------------
# google_oauth.verify_google_id_token
# ---------------------------------------------------------------------------


def test_verify_disabled_when_client_id_blank(monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "")
    with pytest.raises(AppError) as exc:
        verify_google_id_token("anything")
    assert exc.value.code == "GOOGLE_SIGNIN_DISABLED"
    assert exc.value.status_code == 503


def test_verify_forged_token_surfaces_invalid(monkeypatch):
    def boom(_cred, _req, _aud):
        raise ValueError("signature mismatch")
    monkeypatch.setattr(google_oauth.google_id_token, "verify_oauth2_token", boom)
    with pytest.raises(AppError) as exc:
        verify_google_id_token("forged.jwt.token")
    assert exc.value.code == "INVALID_TOKEN"
    assert exc.value.status_code == 401


def test_verify_bad_issuer_surfaces_invalid(monkeypatch):
    monkeypatch.setattr(
        google_oauth.google_id_token, "verify_oauth2_token",
        lambda _c, _r, _a: {"iss": "https://evil.example.com", "email": "x@example.com"},
    )
    with pytest.raises(AppError) as exc:
        verify_google_id_token("token")
    assert exc.value.code == "INVALID_TOKEN"


def test_verify_missing_email_surfaces_invalid(monkeypatch):
    monkeypatch.setattr(
        google_oauth.google_id_token, "verify_oauth2_token",
        lambda _c, _r, _a: {"iss": "accounts.google.com"},  # no email
    )
    with pytest.raises(AppError) as exc:
        verify_google_id_token("token")
    assert exc.value.code == "INVALID_TOKEN"


def test_verify_returns_lowercased_profile(monkeypatch):
    monkeypatch.setattr(
        google_oauth.google_id_token, "verify_oauth2_token",
        lambda _c, _r, _a: {
            "iss": "accounts.google.com",
            "sub": "S-1",
            "email": "Mixed.Case@Example.com",
            "email_verified": True,
            "name": "Jane Doe",
        },
    )
    profile = verify_google_id_token("token")
    assert profile.sub == "S-1"
    assert profile.email == "mixed.case@example.com"
    assert profile.email_verified is True
    assert profile.full_name == "Jane Doe"


# ---------------------------------------------------------------------------
# auth_service.google_login
# ---------------------------------------------------------------------------


def test_google_login_unverified_google_email_rejected(db, monkeypatch):
    _patch_verify(monkeypatch, _profile(email_verified=False))
    with pytest.raises(AppError) as exc:
        auth_service.google_login("cred", "1.2.3.4", "ua", db)
    assert exc.value.code == "EMAIL_NOT_VERIFIED"
    assert db.query(User).count() == 0  # nothing created


def test_google_login_creates_new_user(db, monkeypatch):
    _patch_verify(monkeypatch, _profile())
    res = auth_service.google_login("cred", "1.2.3.4", "ua", db)

    user = db.query(User).filter(User.email == "user@example.com").one()
    assert user.google_sub == "google-sub-123"
    assert user.auth_provider == "google"
    assert user.password_hash is None
    assert user.email_verified is True
    assert user.role == UserRole.user
    assert user.account_status == AccountStatus.active
    assert res.access_token and res.refresh_token
    assert res.user.email == "user@example.com"


def test_google_login_links_to_verified_existing_account(db, monkeypatch):
    existing = User(
        email="user@example.com",
        full_name="Local User",
        password_hash="hashed-secret",
        email_verified=True,
    )
    db.add(existing)
    db.commit()

    _patch_verify(monkeypatch, _profile())
    res = auth_service.google_login("cred", "ip", "ua", db)

    assert db.query(User).count() == 1  # no duplicate
    existing = db.query(User).one()
    assert existing.google_sub == "google-sub-123"  # linked
    assert existing.password_hash == "hashed-secret"  # password untouched
    assert existing.email_verified is True  # held, not promoted as a side-effect
    assert res.user.email == "user@example.com"


def test_google_login_refuses_to_link_unverified_account(db, monkeypatch):
    """Security rule: a Google account must not adopt an unverified local account."""
    existing = User(
        email="user@example.com",
        full_name="Local User",
        password_hash="hashed-secret",
        email_verified=False,
    )
    db.add(existing)
    db.commit()

    _patch_verify(monkeypatch, _profile())
    with pytest.raises(AppError) as exc:
        auth_service.google_login("cred", "ip", "ua", db)
    assert exc.value.code == "EMAIL_NOT_VERIFIED"

    existing = db.query(User).one()
    # Account is untouched: no google_sub, still unverified, password intact.
    assert existing.google_sub is None
    assert existing.email_verified is False
    assert existing.password_hash == "hashed-secret"


def test_google_login_returning_user_relinks_without_duplicate(db, monkeypatch):
    user = User(
        email="user@example.com",
        full_name="Jane",
        password_hash=None,
        google_sub="google-sub-123",
        auth_provider="google",
        email_verified=True,
    )
    db.add(user)
    db.commit()

    _patch_verify(monkeypatch, _profile())
    auth_service.google_login("cred", "ip", "ua", db)

    assert db.query(User).count() == 1
    assert db.query(User).one().google_sub == "google-sub-123"


@pytest.mark.parametrize("status, code", [
    (AccountStatus.suspended, "FORBIDDEN"),
    (AccountStatus.deleted, "ACCOUNT_DELETED"),
])
def test_google_login_rejects_suspended_and_deleted(db, monkeypatch, status, code):
    user = User(
        email="user@example.com",
        full_name="Jane",
        password_hash=None,
        google_sub="google-sub-123",
        auth_provider="google",
        email_verified=True,
        account_status=status,
    )
    db.add(user)
    db.commit()

    _patch_verify(monkeypatch, _profile())
    with pytest.raises(AppError) as exc:
        auth_service.google_login("cred", "ip", "ua", db)
    assert exc.value.code == code


def test_google_login_disabled_config(db, monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "google_client_id", "")
    # verify_google_id_token raises GOOGLE_SIGNIN_DISABLED when called; simulate
    # by patching to the real function path used by auth_service.
    monkeypatch.setattr(auth_service, "verify_google_id_token", verify_google_id_token)
    with pytest.raises(AppError) as exc:
        auth_service.google_login("cred", "ip", "ua", db)
    assert exc.value.code == "GOOGLE_SIGNIN_DISABLED"

def test_password_login_explains_deleted_account_only_after_valid_password(db):
    user = User(
        email="deleted@example.com",
        full_name="Deleted User",
        password_hash=hash_password("Password1!"),
        email_verified=True,
        account_status=AccountStatus.deleted,
    )
    db.add(user)
    db.commit()

    with pytest.raises(AppError) as exc:
        auth_service.login(LoginRequest(email=user.email, password="Password1!"), "ip", "ua", db)

    assert exc.value.code == "ACCOUNT_DELETED"
    assert exc.value.status_code == 403
