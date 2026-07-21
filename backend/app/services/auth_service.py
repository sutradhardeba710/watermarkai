"""Auth business logic (SRS AUTH-001..007, SEC-001)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_short,
    is_strong_password,
    refresh_expiry,
    verify_password,
    verify_refresh_token,
)
from app.core.tokens import (
    RESET_TTL_SECONDS as RESET_TTL,
    decode_email_verification_token,
    make_email_verification_token,
    make_password_reset_token,
)
from app.models import AccountStatus, Session as SessionRow, User, UserRole
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserPublic,
)

settings = get_settings()


# Re-export so callers keep a single entrypoint (auth_service.X).
__all__ = [
    "make_email_verification_token",
    "decode_email_verification_token",
    "make_password_reset_token",
    "register",
    "verify_email",
    "login",
    "refresh_session",
    "logout",
    "forgot_password",
    "reset_password",
]


def _store_reset_nonce(user_id: str, nonce: str) -> None:
    import redis

    redis.from_url(settings.redis_url).setex(f"pwreset:{user_id}:{nonce}", RESET_TTL, "1")


def _consume_reset_nonce(user_id: str, nonce: str) -> bool:
    import redis

    return bool(redis.from_url(settings.redis_url).delete(f"pwreset:{user_id}:{nonce}"))


def _consume_reset_token(token: str) -> str:
    """Decode reset token and consume its one-time nonce in Redis."""
    from jose import JWTError, jwt

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise AppError("INVALID_TOKEN", "Invalid or expired reset link.", 400) from exc
    if payload.get("type") != "password_reset":
        raise AppError("INVALID_TOKEN", "Invalid reset token.", 400)
    user_id = payload["sub"]
    nonce = payload.get("nonce")
    if not nonce:
        raise AppError("INVALID_TOKEN", "Invalid reset token.", 400)
    if not _consume_reset_nonce(user_id, nonce):
        raise AppError("INVALID_TOKEN", "Reset link already used or expired.", 400)
    return user_id


# --- Register (AUTH-001) ---


def register(req: RegisterRequest, db: Session) -> UserPublic:
    if not is_strong_password(req.password):
        raise AppError("WEAK_PASSWORD", "Password does not meet complexity requirements.", 422)
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise AppError("EMAIL_EXISTS", "An account with this email already exists.", 409)
    user = User(
        email=req.email.lower(),
        full_name=req.full_name.strip(),
        password_hash=hash_password(req.password),
        email_verified=False,
        role=UserRole.user,
        account_status=AccountStatus.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # AUTH-002: verification email. MVP stubs to console.
    token = make_email_verification_token(user.id)
    _send_email(user.email, "Verify your email", f"{settings.app_base_url}/verify-email?token={token}")
    return UserPublic.model_validate(user)


# --- Verify email (AUTH-002) ---


def verify_email(token: str, db: Session) -> UserPublic:
    user_id = decode_email_verification_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    if user.email_verified:
        return UserPublic.model_validate(user)
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


# --- Login (AUTH-003) ---


def login(req: LoginRequest, ip: str, user_agent: str, db: Session) -> AuthResponse:
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    if user.account_status == AccountStatus.deleted:
        # Deleted accounts must not receive sessions/tokens; present as bad creds
        # rather than leaking that the account existed.
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    if user.account_status == AccountStatus.suspended:
        raise AppError("FORBIDDEN", "Account suspended.", 403)
    if not user.email_verified:
        # AUTH-002: unverified cannot process video. We still allow login so they
        # can verify, but flag it. Frontend will block /analyze & /process.
        raise AppError("EMAIL_NOT_VERIFIED", "Please verify your email before logging in.", 403)
    user.last_login_at = datetime.now(timezone.utc)
    return _issue_session(user, ip, user_agent, db)


def _issue_session(user: User, ip: str, user_agent: str, db: Session) -> AuthResponse:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    session = SessionRow(
        user_id=user.id,
        refresh_token_hash=hash_short(refresh),
        user_agent=user_agent[:512] if user_agent else None,
        ip_hash=hash_short(ip) if ip else None,
        expires_at=refresh_expiry(),
        revoked=False,
    )
    db.add(session)
    db.commit()
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserPublic.from_user(user),
    )


# --- Refresh (AUTH-006) ---

# Rotation grace: after a refresh token is rotated, the *old* token stays
# usable for this many seconds. Two tabs refreshing at the same instant (both
# holding the same token when the 30-min access token expires) is normal — the
# losing tab must get a fresh session, not a forced logout. Explicit logout
# still revokes immediately (revoked=True bypasses the grace).
_ROTATION_GRACE_SECONDS = 60


def refresh_session(refresh_token: str, db: Session) -> AuthResponse:
    try:
        payload = verify_refresh_token(refresh_token)
    except JWTError as exc:
        raise AppError("UNAUTHORIZED", "Invalid or expired refresh token.", 401) from exc
    user_id = payload["sub"]
    jti = payload.get("jti", "")
    now = datetime.now(timezone.utc)
    session = (
        db.query(SessionRow)
        .filter(SessionRow.user_id == user_id, SessionRow.refresh_token_hash == hash_short(refresh_token))
        .first()
    )
    if session is None or session.revoked:
        raise AppError("UNAUTHORIZED", "Session not found or expired.", 401)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise AppError("UNAUTHORIZED", "Session not found or expired.", 401)
    # Rotate: instead of revoking instantly, collapse the old session's expiry
    # to the grace window so a concurrent tab's in-flight refresh still lands.
    grace_expiry = now + timedelta(seconds=_ROTATION_GRACE_SECONDS)
    if expires_at > grace_expiry:
        session.expires_at = grace_expiry
    user = db.get(User, user_id)
    if user is None or user.account_status != AccountStatus.active:
        raise AppError("UNAUTHORIZED", "Account unavailable.", 401)
    return _issue_session(user, "", "", db)


# --- Logout (AUTH-006) ---


def logout(refresh_token: str | None, db: Session) -> None:
    if not refresh_token:
        return
    try:
        payload = verify_refresh_token(refresh_token)
    except JWTError:
        return
    session = (
        db.query(SessionRow)
        .filter(
            SessionRow.user_id == payload["sub"],
            SessionRow.refresh_token_hash == hash_short(refresh_token),
        )
        .first()
    )
    if session:
        session.revoked = True
        db.commit()


# --- Forgot / reset password (AUTH-004/005) ---


def forgot_password(email: str, db: Session) -> str:
    user = db.query(User).filter(User.email == email.lower()).first()
    # Do not leak existence — always return success.
    if user is None:
        return "If that email exists, a reset link has been sent."
    token, nonce = make_password_reset_token(user.id)
    _store_reset_nonce(user.id, nonce)
    _send_email(user.email, "Reset your password", f"{settings.app_base_url}/reset-password?token={token}")
    return "If that email exists, a reset link has been sent."


def reset_password(req: ResetPasswordRequest, db: Session) -> UserPublic:
    if not is_strong_password(req.password):
        raise AppError("WEAK_PASSWORD", "Password does not meet complexity requirements.", 422)
    user_id = _consume_reset_token(req.token)
    user = db.get(User, user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    user.password_hash = hash_password(req.password)
    # Revoke all existing sessions for this user (force re-login).
    db.query(SessionRow).filter(SessionRow.user_id == user_id).update({"revoked": True})
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


# --- Email stub (AUTH-002) ---


def _send_email(to: str, subject: str, body: str) -> None:
    # MVP: console log. Switch to SMTP when VWA_SMTP_CONSOLE=false.
    # flush=True: stdout is block-buffered when redirected to a file, so without
    # this the verification link never reaches the live log window.
    if settings.smtp_console:
        print(f"[email] to={to} subject={subject}\nbody={body}\n", flush=True)
        return
    # Real SMTP wired later; left as a no-op guard so dev never crashes.
    print(f"[email:disabled] to={to} subject={subject}", flush=True)
