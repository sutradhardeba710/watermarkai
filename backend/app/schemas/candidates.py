"""Phase 7 detection schemas (SRS DETECT-001..007, AI-001/002/004/006).

Pydantic shapes for:
  POST /api/v1/projects/{id}/analyze     -> enqueue an analyze job
  GET  /api/v1/projects/{id}/candidates  -> ranked detection candidates
  GET  /api/v1/candidates/{id}           -> one candidate (UI slide-over)
  POST /api/v1/candidates/{id}/approve   -> promote a candidate to a mask

Pydantic v2 (BaseModel + ``model_config``); the project no longer mixes v1
helpers. The analyze trigger takes its overrides via query parameters (rerun,
sample_fps), so a dedicated request body schema isn't needed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


ANALYZE_SAMPLE_FPS_VALUES = {0.5, 1.0, 2.0}


class AnalyzeResponse(BaseModel):
    """Returns the job id immediately; clients open the SSE stream off the
    ProcessingJob table (same id space as Phase 5's process jobs)."""
    job_id: str
    project_id: str
    status: str
    model_config = {"from_attributes": True}


class CandidateResponse(BaseModel):
    id: str
    project_id: str
    candidate_type: str
    confidence: float
    bounding_box: dict
    is_static: bool
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    tracking_data: Optional[dict] = None
    user_approved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateListResponse(BaseModel):
    project_id: str
    candidates: list[CandidateResponse] = Field(default_factory=list)
    needs_manual_selection: bool = False
    notes: Optional[str] = None


class ApproveCandidateRequest(BaseModel):
    """Optional tune-ahead on promote (DETECT-007 lets the user tweak the
    candidate before it becomes the active mask). Empty body is allowed."""
    mask_expansion: int = Field(default=0, ge=-100, le=100)
    mask_feathering: int = Field(default=4, ge=0, le=50)
    temporal_smoothing: bool = False


class ApproveCandidateResponse(BaseModel):
    candidate_id: str
    project_id: str
    mask_id: str
    message: str = "Candidate promoted to mask."
    model_config = {"from_attributes": True}


__all__ = [
    "ANALYZE_SAMPLE_FPS_VALUES",
    "AnalyzeResponse",
    "CandidateResponse",
    "CandidateListResponse",
    "ApproveCandidateRequest",
    "ApproveCandidateResponse",
]
