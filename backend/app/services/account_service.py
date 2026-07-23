"""Self-service account management (edit profile, password, avatar, delete).

Distinct from ``auth_service`` (registration/login/reset). Everything here acts
on the *currently authenticated* user resolved by ``get_current_user``.
"""
from __future__ import annotations

import io
import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, is_strong_password, verify_password
from app.models import AccountStatus, Session as SessionRow, User
from app.schemas.auth import (
    ChangePasswordRequest,
    UpdateProfileRequest,
    UserPublic,
)
from app.services import email_service
from app.storage.factory import get_storage

AVATAR_BUCKET = "avatars"
# Avatars are small profile images; keep the cap tight so a stray large upload
# can't fill local storage. 5 MB comfortably covers any reasonable photo.
MAX_AVATAR_BYTES = 5 * 1024 * 1024
_ALLOWED_AVATAR_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def update_profile(user: User, req: UpdateProfileRequest, db: Session) -> UserPublic:
    user.full_name = req.full_name.strip()
    db.commit()
    db.refresh(user)
    return UserPublic.from_user(user)


def change_password(user: User, req: ChangePasswordRequest, db: Session) -> None:
    if user.password_hash is None:
        # Google-only account, nothing to compare "current_password" against.
        # They can add one via the forgot-password flow, which sets a fresh
        # password_hash without requiring an old one.
        raise AppError(
            "NO_PASSWORD_SET",
            "This account has no password yet. Use \"Forgot password\" to set one.",
            400,
        )
    if not verify_password(req.current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Your current password is incorrect.", 401)
    if not is_strong_password(req.new_password):
        raise AppError("WEAK_PASSWORD", "New password does not meet complexity requirements.", 422)
    user.password_hash = hash_password(req.new_password)
    # Force other devices to re-authenticate after a password change, but keep
    # the caller's own session valid so they aren't logged out mid-request.
    db.query(SessionRow).filter(SessionRow.user_id == user.id).update({"revoked": True})
    db.commit()
    email_service.queue_email(user.email, "password_changed", {"name": user.full_name})


def set_avatar(user: User, content_type: str | None, data: bytes, db: Session) -> UserPublic:
    ext = _ALLOWED_AVATAR_TYPES.get((content_type or "").lower())
    if ext is None:
        raise AppError("UNSUPPORTED_MEDIA", "Avatar must be a JPEG, PNG, or WebP image.", 415)
    if not data:
        raise AppError("EMPTY_FILE", "The uploaded image is empty.", 422)
    if len(data) > MAX_AVATAR_BYTES:
        raise AppError("FILE_TOO_LARGE", "Avatar images must be 5 MB or smaller.", 413)

    storage = get_storage()
    # New unique key each upload so browsers don't serve a stale cached image.
    new_key = f"{user.id}/{uuid.uuid4().hex}.{ext}"
    storage.put(AVATAR_BUCKET, new_key, io.BytesIO(data), content_type=content_type)

    old_key = user.avatar_key
    user.avatar_key = new_key
    db.commit()
    db.refresh(user)

    if old_key and old_key != new_key:
        _safe_delete(old_key)
    return UserPublic.from_user(user)


def remove_avatar(user: User, db: Session) -> UserPublic:
    old_key = user.avatar_key
    user.avatar_key = None
    db.commit()
    db.refresh(user)
    if old_key:
        _safe_delete(old_key)
    return UserPublic.from_user(user)


def delete_account(user: User, password: str, db: Session) -> None:
    """Soft delete: flag the account and revoke every session. Login/auth already
    treat ``account_status == deleted`` as unavailable, so no data is destroyed
    and an admin can reverse it."""
    # Google-only accounts have no password to confirm with — the caller is
    # already holding a valid access token, which is the confirmation.
    if user.password_hash is not None and not verify_password(password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Password is incorrect.", 401)
    user.account_status = AccountStatus.deleted
    db.query(SessionRow).filter(SessionRow.user_id == user.id).update({"revoked": True})
    db.commit()
    email_service.queue_email(user.email, "account_deleted", {"name": user.full_name})


def _safe_delete(key: str) -> None:
    try:
        get_storage().delete(AVATAR_BUCKET, key)
    except Exception:  # noqa: BLE001 — a leftover avatar file is harmless
        pass


__all__ = [
    "AVATAR_BUCKET",
    "MAX_AVATAR_BYTES",
    "update_profile",
    "change_password",
    "set_avatar",
    "remove_avatar",
    "delete_account",
]
