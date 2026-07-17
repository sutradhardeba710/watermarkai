"""Preview / download schemas (SRS PREVIEW-001..006, DOWNLOAD-001..005).

Pydantic models for Phase 6 endpoints:
  - POST /api/v1/projects/{id}/preview         -> request + response
  - GET  /api/v1/projects/{id}/preview         -> artifact descriptor
  - POST /api/v1/projects/{id}/download-url    -> signed URL request + response
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


ALLOWED_DURATIONS = {3, 5, 10}
PROGRESS_STAGES = {"queued", "processing", "ready", "failed"}


class PreviewRequest(BaseModel):
    """Body for POST /projects/{id}/preview. Optional window params.

    * `start_seconds` defaults to the inpaint-time watermark range start (or 0).
    * `duration_seconds` defaults to 5s; allowed values are 3, 5, or 10.
    """
    start_seconds: Optional[float] = Field(default=None, ge=0)
    duration_seconds: int = Field(default=5)

    @field_validator("duration_seconds")
    @classmethod
    def _check_duration(cls, v: int) -> int:
        if v not in ALLOWED_DURATIONS:
            raise ValueError(f"duration_seconds must be one of {sorted(ALLOWED_DURATIONS)}")
        return v

    @field_validator("start_seconds")
    @classmethod
    def _check_start(cls, v: float | None) -> float | None:
        if v is None:
            return v
        # The endpoint re-checks against the project's duration; here we only
        # ensure the value isn't absurd.
        if v > 60 * 60 * 24:
            raise ValueError("start_seconds is unreasonably large")
        return v


class PreviewResponse(BaseModel):
    """Returned by POST /preview — preview status + where to fetch it."""
    project_id: str
    status: str  # queued | processing | ready | failed
    quality_mode: str
    start_seconds: float
    duration_seconds: int
    artifact_storage_key: Optional[str] = None
    before_artifact_storage_key: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class DownloadUrlRequest(BaseModel):
    """Body for POST /projects/{id}/download-url. Clamped to the configured cap."""
    expires_seconds: int = Field(default=1800, ge=60)

    @field_validator("expires_seconds")
    @classmethod
    def _check_expiry(cls, v: int) -> int:
        if v > 24 * 3600:
            raise ValueError("expires_seconds cannot exceed 24h")
        return v


class DownloadUrlResponse(BaseModel):
    bucket: str
    key: str
    url: str
    expires_seconds: int
    expires_at: datetime


__all__ = [
    "PreviewRequest",
    "PreviewResponse",
    "DownloadUrlRequest",
    "DownloadUrlResponse",
    "ALLOWED_DURATIONS",
    "PROGRESS_STAGES",
]
