"""Upload + project create schemas (SRS UPLOAD, META, LEGAL)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.projects import ProjectDetail


class ProjectCreateRequest(BaseModel):
    title: Optional[str] = None
    filename: str = Field(min_length=1, max_length=512)
    total_bytes: Optional[int] = Field(default=None, ge=0)


class UploadInitiateRequest(BaseModel):
    project_id: str
    filename: str = Field(min_length=1, max_length=512)
    total_bytes: Optional[int] = Field(default=None, ge=0)
    content_type: Optional[str] = None


class UploadInitiateResponse(BaseModel):
    upload_id: str
    project_id: str
    storage_key: str
    bucket: str
    chunked: bool
    upload_url: Optional[str] = None  # presigned URL for S3/MinIO backends

    model_config = {"from_attributes": True}


class UploadCompleteRequest(BaseModel):
    total_bytes: Optional[int] = Field(default=None, ge=0)


class UploadCompleteResponse(BaseModel):
    upload_id: str
    project_id: str
    received_bytes: int
    completed: bool
    project: ProjectDetail


class ComplianceConfirmRequest(BaseModel):
    ownership_confirmed: bool = True
    intended_use: Optional[str] = Field(default=None, max_length=512)
    policy_version: str = "1.0"


class ComplianceConfirmResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    confirmation_version: str
    confirmed_at: datetime

    model_config = {"from_attributes": True}


# Resolve the forward ref to avoid runtime NameError when the body model is built.
UploadCompleteResponse.model_rebuild()
