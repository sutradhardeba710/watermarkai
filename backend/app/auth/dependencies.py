"""FastAPI dependencies: current user extraction, role guard, project ownership.

SRS AUTH-007, SEC-003, SEC-009.
"""
from __future__ import annotations

from fastapi import Depends, Header, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import verify_access_token
from app.models import AccountStatus, User, UserRole


def get_authorization_scheme(authorization: str | None) -> tuple[str | None, str | None]:
    if not authorization:
        return None, None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, None
    return "bearer", parts[1].strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    scheme, token = get_authorization_scheme(authorization)
    if not token:
        raise AppError("UNAUTHORIZED", "Missing or invalid authorization header.", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = verify_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AppError("UNAUTHORIZED", "Invalid or expired token.", status.HTTP_401_UNAUTHORIZED) from exc

    user = db.get(User, payload["sub"])
    if user is None:
        raise AppError("UNAUTHORIZED", "User not found.", status.HTTP_401_UNAUTHORIZED)
    if user.account_status == AccountStatus.suspended:
        raise AppError("FORBIDDEN", "Account suspended.", status.HTTP_403_FORBIDDEN)
    if user.account_status == AccountStatus.deleted:
        raise AppError("UNAUTHORIZED", "Account deleted.", status.HTTP_401_UNAUTHORIZED)
    return user


def require_role(*roles: UserRole):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "Insufficient permissions.", status.HTTP_403_FORBIDDEN)
        return user

    return dep


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise AppError("FORBIDDEN", "Admin access required.", status.HTTP_403_FORBIDDEN)
    return user
