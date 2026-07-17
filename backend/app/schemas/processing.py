"""Processing / job schemas (SRS PROCESS-001..008, ENCODE, REL).

Pydantic models for the Phase 5 processing endpoints:
  - POST /api/v1/projects/{id}/process      -> enqueue a `process` job
  - GET  /api/v1/jobs/{id}/status          -> poll snapshot
  - GET  /api/v1/jobs/{id}/events           -> SSE progress stream (PROCESS-003)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


QUALITY_VALUES = {"fast", "balanced", "high"}


class ProcessSettingsRequest(BaseModel):
    """Optional overrides submitted with POST /process. Anything omitted falls
    back to the project's stored ProcessingSetting (or the defaults)."""
    quality_mode: str = Field(default="balanced")
    mask_expansion: Optional[int] = None
    mask_feathering: Optional[int] = None
    temporal_smoothing: Optional[bool] = None
    output_resolution: Optional[str] = Field(default=None, max_length=32)
    preserve_audio: bool = True

    @field_validator("quality_mode")
    @classmethod
    def _check_quality(cls, v: str) -> str:
        if v not in QUALITY_VALUES:
            raise ValueError(f"quality_mode must be one of {sorted(QUALITY_VALUES)}")
        return v

    @field_validator("mask_expansion")
    @classmethod
    def _check_expansion(cls, v: int | None) -> int | None:
        if v is not None and not (-100 <= v <= 100):
            raise ValueError("mask_expansion must be between -100 and 100")
        return v

    @field_validator("mask_feathering")
    @classmethod
    def _check_feather(cls, v: int | None) -> int | None:
        if v is not None and not (0 <= v <= 50):
            raise ValueError("mask_feathering must be between 0 and 50")
        return v


class ProcessRequest(BaseModel):
    """Body for POST /projects/{id}/process. Empty body is allowed (uses stored
    settings / defaults)."""
    settings: ProcessSettingsRequest = Field(default_factory=ProcessSettingsRequest)


class ProcessResponse(BaseModel):
    """Returned immediately after enqueue — the job id so the client can open the
    SSE stream."""
    job_id: str
    project_id: str
    status: str
    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Snapshot of a processing job for polling."""
    id: str
    project_id: str
    job_type: str
    status: str
    progress: int
    current_stage: Optional[str] = None
    processing_mode: str
    frames_processed: int
    total_frames: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class JobEvent(BaseModel):
    """Single SSE event payload (PROCESS-003: stage, %, frames processed, total,
    warnings). Serialised as `data: <json>\\n\\n` on the SSE stream."""
    stage: str
    progress: int
    frames_processed: int = 0
    total_frames: int = 0
    warnings: list[str] = Field(default_factory=list)
    message: Optional[str] = None
    terminal: bool = False
    error_code: Optional[str] = None


__all__ = [
    "ProcessRequest",
    "ProcessSettingsRequest",
    "ProcessResponse",
    "JobStatusResponse",
    "JobEvent",
    "QUALITY_VALUES",
]
