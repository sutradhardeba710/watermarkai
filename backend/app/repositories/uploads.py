"""Upload + project repositories (SRS UPLOAD, META, LEGAL).

Thin data-access layer over the ORM. The route/service layer composes these
with validation + storage so the SQL is testable in isolation.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ComplianceConfirmation,
    ProjectStatus,
    Upload,
    VideoProject,
    WatermarkMask,
)


def create_project(
    db: Session,
    user_id: str,
    title: str,
    original_filename: str,
    total_bytes: int | None = None,
) -> VideoProject:
    project = VideoProject(
        user_id=user_id,
        title=title or original_filename,
        original_filename=original_filename,
        file_size=total_bytes,
        status=ProjectStatus.uploading,
    )
    db.add(project)
    db.flush()
    return project


def create_upload(
    db: Session,
    project_id: str,
    user_id: str,
    filename: str,
    total_bytes: int | None = None,
) -> Upload:
    upload = Upload(
        project_id=project_id,
        user_id=user_id,
        filename=filename,
        total_bytes=total_bytes,
    )
    db.add(upload)
    db.flush()
    return upload


def get_upload(db: Session, upload_id: str) -> Upload | None:
    return db.get(Upload, upload_id)


def get_project(db: Session, project_id: str) -> VideoProject | None:
    return db.get(VideoProject, project_id)


def get_project_owned(db: Session, project_id: str, user_id: str) -> VideoProject | None:
    p = db.get(VideoProject, project_id)
    if p is None or p.user_id != user_id or p.deleted:
        return None
    return p


def set_upload_progress(db: Session, upload: Upload, received: int) -> None:
    upload.received_bytes = received
    db.flush()


def finalize_upload(
    db: Session,
    upload: Upload,
    storage_key: str,
    received_bytes: int,
) -> Upload:
    upload.storage_key = storage_key
    upload.received_bytes = received_bytes
    upload.completed = True
    db.flush()
    return upload


def attach_metadata(
    db: Session, project: VideoProject, meta: dict[str, Any]
) -> VideoProject:
    project.duration = meta.get("duration")
    project.width = meta.get("width")
    project.height = meta.get("height")
    project.fps = meta.get("fps")
    project.frame_count = meta.get("frame_count")
    project.video_codec = meta.get("video_codec")
    project.audio_codec = meta.get("audio_codec")
    project.has_audio = meta.get("has_audio")
    db.flush()
    return project


def mark_status(db: Session, project: VideoProject, status: ProjectStatus) -> VideoProject:
    project.status = status
    db.flush()
    return project


def mark_completed(db: Session, project: VideoProject, status: ProjectStatus = ProjectStatus.uploaded) -> VideoProject:
    project.status = status
    db.flush()
    return project


def cancel_upload(db: Session, upload: Upload) -> Upload:
    """Cancel an in-flight partial upload (UPLOAD-007)."""
    upload.completed = False
    db.flush()
    return upload


def record_confirmation(
    db: Session,
    user_id: str,
    project_id: str,
    policy_version: str = "1.0",
    ip_hash: str | None = None,
    user_agent: str | None = None,
) -> ComplianceConfirmation:
    conf = ComplianceConfirmation(
        user_id=user_id,
        project_id=project_id,
        confirmation_version=policy_version,
        ip_hash=ip_hash,
        user_agent=user_agent,
    )
    db.add(conf)
    db.flush()
    return conf


def has_confirmation(db: Session, project_id: str) -> bool:
    stmt = select(ComplianceConfirmation.id).where(
        ComplianceConfirmation.project_id == project_id
    ).limit(1)
    return db.execute(stmt).first() is not None


# --- Masks (SRS MASK) ---


def save_mask(db: Session, project: VideoProject, **fields) -> WatermarkMask:
    """Replace any existing mask for the project with one row."""
    db.query(WatermarkMask).filter(WatermarkMask.project_id == project.id).delete()
    mask = WatermarkMask(project_id=project.id, **fields)
    db.add(mask)
    db.flush()
    return mask


def latest_mask(db: Session, project_id: str) -> WatermarkMask | None:
    return (
        db.query(WatermarkMask)
        .filter(WatermarkMask.project_id == project_id)
        .order_by(WatermarkMask.created_at.desc())
        .first()
    )


__all__ = [
    "create_project",
    "create_upload",
    "get_upload",
    "get_project",
    "get_project_owned",
    "set_upload_progress",
    "finalize_upload",
    "attach_metadata",
    "mark_status",
    "mark_completed",
    "cancel_upload",
    "record_confirmation",
    "has_confirmation",
    "save_mask",
    "latest_mask",
]
