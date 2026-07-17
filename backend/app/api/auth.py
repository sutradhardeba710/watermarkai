"""Auth routes (SRS §15, BE-007 rate limiting)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.db import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.services import auth_service

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
    return UserPublic.model_validate(user)
