"""Project schemas (DASH-002)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    title: str
    original_filename: str
    status: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    progress: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    proxy_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectDetail(ProjectSummary):
    fps: Optional[float] = None
    frame_count: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: Optional[bool] = None
    file_size: Optional[int] = None
    proxy_storage_key: Optional[str] = None
    thumbnail_storage_key: Optional[str] = None
    input_storage_key: Optional[str] = None
    output_storage_key: Optional[str] = None
    preview_storage_key: Optional[str] = None
    # Short-lived signed URLs for raw <video>/<img> playback (no bearer header
    # can be attached to a media-element src). None until the artifact exists.
    proxy_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    before_preview_url: Optional[str] = None

    model_config = {"from_attributes": True}
