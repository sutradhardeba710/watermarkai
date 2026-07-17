"""Pure unit tests for security utils (no DB/Redis).

Covers SEC-001 password hashing/verification, AUTH-001 strength rules, and the
stateless email-verification token round-trip (AUTH-002).
"""
from __future__ import annotations

import time

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_strong_password,
    verify_password,
    verify_refresh_token,
    verify_access_token,
)
from app.core.tokens import (
    make_email_verification_token,
    decode_email_verification_token,
    make_password_reset_token,
)


def test_password_hash_and_verify():
    h = hash_password("Hunter2!abc")
    assert h != "Hunter2!abc"
    assert verify_password("Hunter2!abc", h) is True
    assert verify_password("wrong", h) is False


@pytest.mark.parametrize(
    "pw, ok",
    [
        ("Abcdef1!", True),
        ("abcdefgh", False),  # no upper, no digit, no special
        ("ABCDEFG1", False),  # no lower, no special
        ("Ab1!", False),  # too short
        ("Abcdefgh!", False),  # no digit
        ("Abcdefg1h", False),  # no special
    ],
)
def test_strong_password(pw: str, ok: bool):
    assert is_strong_password(pw) is ok


def test_access_token_roundtrip():
    tok = create_access_token("user-123", "user")
    payload = verify_access_token(tok)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["role"] == "user"


def test_refresh_token_roundtrip():
    tok = create_refresh_token("user-9")
    payload = verify_refresh_token(tok)
    assert payload["sub"] == "user-9"
    assert payload["type"] == "refresh"


def test_token_type_mismatch_rejected():
    access = create_access_token("u1", "user")
    with pytest.raises(Exception):
        verify_refresh_token(access)


def test_email_verification_token_roundtrip():
    tok = make_email_verification_token("user-xyz")
    uid = decode_email_verification_token(tok)
    assert uid == "user-xyz"


def test_email_verification_token_rejects_wrong_type():
    access = create_access_token("u1", "user")
    with pytest.raises(Exception):
        decode_email_verification_token(access)


def test_password_reset_token_returns_token_and_nonce():
    tok, nonce = make_password_reset_token("user-7")
    assert isinstance(tok, str) and isinstance(nonce, str) and len(nonce) > 8
