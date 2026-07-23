"""Auth routes (SRS §15, BE-007 rate limiting)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.db import get_db
from app.auth.dependencies import get_current_user
from app.core.errors import AppError
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.services import account_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])


class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "0.0.0.0"


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> UserPublic:
    return auth_service.register(req, db)


@router.post("/verify-email", response_model=UserPublic)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)) -> UserPublic:
    return auth_service.verify_email(req.token, db)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    return auth_service.login(req, ip, ua, db)


@router.post("/google", response_model=AuthResponse)
def google_login(req: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    return auth_service.google_login(req.credential, ip, ua, db)


@router.post("/refresh", response_model=AuthResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return auth_service.refresh_session(req.refresh_token, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutBody, db: Session = Depends(get_db)) -> None:
    auth_service.logout(body.refresh_token, db)
    return None


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    return {"message": auth_service.forgot_password(req.email, db)}


@router.post("/reset-password", response_model=UserPublic)
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)) -> UserPublic:
    return auth_service.reset_password(req, db)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.from_user(user)


@router.patch("/me", response_model=UserPublic)
def update_me(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    return account_service.update_profile(user, req, db)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    account_service.change_password(user, req, db)
    return None


@router.post("/me/avatar", response_model=UserPublic)
async def upload_my_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    data = await file.read()
    return account_service.set_avatar(user, file.content_type, data, db)


@router.delete("/me/avatar", response_model=UserPublic)
def delete_my_avatar(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPublic:
    return account_service.remove_avatar(user, db)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    req: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    account_service.delete_account(user, req.password, db)
    return None


@router.get("/avatars/{user_id}/{filename}")
def get_avatar(
    user_id: str,
    filename: str,
    db: Session = Depends(get_db),
):
    """Serve a stored avatar image. Public-by-obscurity: the key embeds a random
    UUID, and only the owner ever learns the URL (returned as avatar_url). This
    lets it drop straight into an <img src> with no Authorization header."""
    key = f"{user_id}/{filename}"
    user = db.get(User, user_id)
    if user is None or user.avatar_key != key:
        raise AppError("NOT_FOUND", "Avatar not found.", status.HTTP_404_NOT_FOUND)

    from app.storage.factory import get_storage
    from app.storage.local_fs import LocalFsStorage
    from app.services.account_service import AVATAR_BUCKET

    ext = filename.rsplit(".", 1)[-1].lower()
    media = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "application/octet-stream")

    storage = get_storage()
    if isinstance(storage, LocalFsStorage):
        from app.core.config import get_settings

        path = (get_settings().storage_local_path / AVATAR_BUCKET / key).resolve()
        if not path.exists():
            raise AppError("NOT_FOUND", "Avatar file missing.", status.HTTP_404_NOT_FOUND)
        return FileResponse(str(path), media_type=media)
    try:
        payload = storage.get(AVATAR_BUCKET, key)
    except Exception as exc:  # noqa: BLE001
        raise AppError("STORAGE_ERROR", "Could not read avatar.", 502) from exc
    return Response(content=payload, media_type=media)
