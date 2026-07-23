"""Auth request/response schemas (SRS AUTH-001..006)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    terms_accepted: bool = Field(default=False)

    @field_validator("terms_accepted")
    @classmethod
    def _must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms to register.")
        return v

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        password = info.data.get("password")
        if password and v != password:
            raise ValueError("Password and confirm password do not match.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    # The signed ID token (JWT) handed to the browser by Google Identity
    # Services' "Sign in with Google" button. Verified server-side in
    # app.core.google_oauth before any claim is trusted.
    credential: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        if info.data.get("password") != v:
            raise ValueError("Password and confirm password do not match.")
        return v


class VerifyEmailRequest(BaseModel):
    token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserPublic"


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    admin_role: Optional[str] = None
    email_verified: bool
    account_status: str
    created_at: datetime
    avatar_url: Optional[str] = None
    auth_provider: str = "local"
    has_password: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserPublic":
        """Build the public view, deriving avatar_url from the stored key and
        has_password from whether a password_hash is set (false for Google-only
        accounts — the frontend uses it to hide the change-password form)."""
        data = cls.model_validate(user)
        if getattr(user, "avatar_key", None):
            data.avatar_url = f"/api/v1/auth/avatars/{user.avatar_key}"
        data.has_password = getattr(user, "password_hash", None) is not None
        return data


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v: str, info) -> str:
        if info.data.get("new_password") != v:
            raise ValueError("New password and confirmation do not match.")
        return v


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class PasswordResetTokenResponse(BaseModel):
    message: str
    # token only returned when SMTP is stubbed to console (dev), otherwise emailed.


AuthResponse.model_rebuild()
