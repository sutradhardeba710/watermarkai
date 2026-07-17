"""Processing-job / settings / output repositories (SRS PROCESS-001..008).

Thin data-access layer over the ORM for the Phase 5 pipeline. Status
transitions live in :func:`_can_transition` so the route layer and the Celery
task can both guard against illegal jumps (PROCESS-002).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    JobState,
    JobType,
    OutputFile,
    ProcessingJob,
    ProcessingSetting,
    ProjectStatus,
    QualityMode,
    VideoProject,
)
from app.services.job_states import can_transition


def create_job(
    db: Session,
    project: VideoProject,
    job_type: JobType = JobType.process,
    quality_mode: QualityMode = QualityMode.balanced,
) -> ProcessingJob:
    job = ProcessingJob(
        project_id=project.id,
        user_id=project.user_id,
        job_type=job_type,
        status=JobState.created,
        processing_mode=quality_mode,
    )
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: str) -> ProcessingJob | None:
    return db.get(ProcessingJob, job_id)


def get_job_owned(db: Session, job_id: str, user_id: str) -> ProcessingJob | None:
    job = db.get(ProcessingJob, job_id)
    if job is None or job.user_id != user_id:
        return None
    return job


def list_jobs_for_project(db: Session, project_id: str) -> list[ProcessingJob]:
    stmt = (
        select(ProcessingJob)
        .where(ProcessingJob.project_id == project_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


def transition(
    db: Session,
    job: ProcessingJob,
    target: JobState,
    *,
    stage: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> ProcessingJob:
    """Apply PROCESS-002 transition with the legal-edge guard. Sets
    started_at/completed_at timestamps and stamps current_stage."""
    if job.status == target:
        # idempotent no-op (e.g. already completed)
        return job
    if not can_transition(job.status, target):
        raise ValueError(f"illegal job transition {job.status.value} -> {target.value}")
    job.status = target
    if stage is not None:
        job.current_stage = stage
    if target in (JobState.processing, JobState.encoding, JobState.preview_processing):
        if job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
    if target in (JobState.completed, JobState.failed, JobState.cancelled, JobState.expired):
        job.completed_at = datetime.now(timezone.utc)
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    db.flush()
    return job


def set_progress(
    db: Session,
    job: ProcessingJob,
    progress: int,
    *,
    frames_processed: int | None = None,
    total_frames: int | None = None,
    stage: str | None = None,
) -> ProcessingJob:
    job.progress = max(0, min(100, int(progress)))
    if frames_processed is not None:
        job.frames_processed = int(frames_processed)
    if total_frames is not None:
        job.total_frames = int(total_frames)
    if stage is not None:
        job.current_stage = stage
    db.flush()
    return job


def mark_failed(
    db: Session,
    job: ProcessingJob,
    code: str,
    message: str,
    *,
    stage: str | None = None,
) -> ProcessingJob:
    return transition(
        db, job, JobState.failed, stage=stage, error_code=code, error_message=message
    )


def fail_project(db: Session, project: VideoProject) -> VideoProject:
    project.status = ProjectStatus.failed
    project.completed_at = datetime.now(timezone.utc)
    db.flush()
    return project


def complete_project(
    db: Session, project: VideoProject, output_storage_key: str
) -> VideoProject:
    project.status = ProjectStatus.completed
    project.output_storage_key = output_storage_key
    project.completed_at = datetime.now(timezone.utc)
    db.flush()
    return project


# --- Settings (PROCESS) ---


def upsert_settings(
    db: Session,
    project: VideoProject,
    *,
    quality_mode: QualityMode = QualityMode.balanced,
    mask_expansion: int = 0,
    mask_feathering: int = 4,
    temporal_smoothing: bool = False,
    output_resolution: str | None = None,
    output_codec: str | None = None,
    preserve_audio: bool = True,
) -> ProcessingSetting:
    """Replace any stored settings row for this project (one row per project)."""
    db.query(ProcessingSetting).filter(ProcessingSetting.project_id == project.id).delete()
    settings = get_settings()
    setting = ProcessingSetting(
        project_id=project.id,
        quality_mode=quality_mode,
        mask_expansion=mask_expansion,
        mask_feathering=mask_feathering,
        temporal_smoothing=temporal_smoothing,
        output_resolution=output_resolution,
        output_codec=output_codec or settings.output_codec,
        preserve_audio=preserve_audio,
    )
    db.add(setting)
    db.flush()
    return setting


def get_settings_row(db: Session, project_id: str) -> ProcessingSetting | None:
    return (
        db.query(ProcessingSetting)
        .filter(ProcessingSetting.project_id == project_id)
        .order_by(ProcessingSetting.created_at.desc())
        .first()
    )


# --- Output files (PROCESS-007) ---


def record_output(
    db: Session,
    project: VideoProject,
    storage_key: str,
    *,
    bucket: str = "outputs",
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
    file_size: int | None = None,
    quality_mode: QualityMode = QualityMode.balanced,
    expires_at: datetime | None = None,
) -> OutputFile:
    settings = get_settings()
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.retain_output_days)
    out = OutputFile(
        project_id=project.id,
        storage_key=storage_key,
        bucket=bucket,
        duration=duration,
        width=width,
        height=height,
        file_size=file_size,
        quality_mode=quality_mode,
        expires_at=expires_at,
    )
    db.add(out)
    db.flush()
    return out


__all__ = [
    "can_transition",
    "create_job",
    "get_job",
    "get_job_owned",
    "list_jobs_for_project",
    "transition",
    "set_progress",
    "mark_failed",
    "fail_project",
    "complete_project",
    "upsert_settings",
    "get_settings_row",
    "record_output",
]
