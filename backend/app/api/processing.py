"""Processing routes (SRS PROCESS-001..008, REL-001).

  POST /api/v1/projects/{id}/process       — enqueue a `process` job (legal +
                                             mask checks -> created/queued).
  GET  /api/v1/projects/{id}/jobs           — job history for a project.
  GET  /api/v1/jobs/{id}/status            — snapshot for polling.
  GET  /api/v1/jobs/{id}/events            — SSE progress stream (PROCESS-003).

The SSE stream reads from a Redis list `job_events:{id}` that the Celery task
publishes to. The route issues a short-history replay first so late clients
still see the event sequence the worker has already emitted, then tails.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import JobState, JobType, QualityMode, User, VideoProject, ProjectStatus
from app.repositories import processing as proc_repo
from app.repositories import uploads as upload_repo
from app.schemas.processing import (
    JobStatusResponse,
    ProcessRequest,
    ProcessResponse,
)
from app.services.compliance import gate_unconfirmed

settings = get_settings()

project_router = APIRouter(prefix="/projects", tags=["processing"])
jobs_router = APIRouter(prefix="/jobs", tags=["processing"])


def _owned_ready_project(db: Session, project_id: str, user: User) -> VideoProject:
    """Owner + state guards shared by the process endpoint."""
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if p.status in (ProjectStatus.uploading, ProjectStatus.created):
        raise AppError("CONFLICT", "Project has not finished uploading yet.", 409)
    if not p.width or not p.height:
        raise AppError("CONFLICT", "Project metadata not available yet (ffprobe).", 409)
    return p


def _require_mask(db: Session, project_id: str):
    mask = upload_repo.latest_mask(db, project_id)
    if mask is None:
        raise AppError("MASK_REQUIRED", "Save a watermark mask before processing.", 422)
    return mask


# A created/processing_queued job older than this with no worker ever having
# started it is treated as dead — its Celery message is no longer in the queue
# (worker was down at enqueue time, or died mid-flight without acking), so
# returning it would permanently block the idempotent enqueue path and leave
# the UI stuck on "queued · 0% (0/0 frames)".
_STALE_QUEUE_SECONDS = 300


def _active_job(db: Session, project_id: str):
    """A genuinely-active job already attached to this project.

    `processing`/`encoding` jobs are always considered active (a worker owns
    them). A `created`/`processing_queued` job is active only if it started
    recently; older ones with `started_at=None` are cancelled here so a fresh
    Approve can enqueue instead of short-circuiting on a dead row.
    """
    jobs = proc_repo.list_jobs_for_project(db, project_id)
    now = datetime.now(timezone.utc)
    for j in jobs:
        if j.status in (JobState.processing, JobState.encoding):
            return j
        if j.status in (JobState.created, JobState.processing_queued):
            started = j.started_at
            age = (now - started) if started is not None else None
            if started is not None and age is not None and age < timedelta(seconds=_STALE_QUEUE_SECONDS):
                return j
            # Stale: no worker picked it up within the window. Cancel so the
            # caller enqueues a fresh job.
            proc_repo.transition(
                db, j, JobState.cancelled,
                stage=j.current_stage,
                error_code="STALE_QUEUED",
                error_message="Enqueued but never picked up by a worker; re-approve to retry.",
            )
            db.commit()
    return None


@project_router.post("/{project_id}/process", response_model=ProcessResponse)
def enqueue_process(
    project_id: str,
    body: ProcessRequest | None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProcessResponse:
    p = _owned_ready_project(db, project_id, user)

    # LEGAL-003: gate behind ownership confirmation.
    gate_unconfirmed(upload_repo.has_confirmation(db, p.id))
    _require_mask(db, p.id)

    # Idempotent: one active job per project.
    existing = _active_job(db, p.id)
    if existing is not None:
        return ProcessResponse(job_id=existing.id, project_id=p.id, status=existing.status.value)

    overrides = (body.settings if body is not None else None)
    quality = QualityMode(overrides.quality_mode) if overrides else QualityMode.balanced
    proc_repo.upsert_settings(
        db, p,
        quality_mode=quality,
        mask_expansion=overrides.mask_expansion if overrides else 0,
        mask_feathering=overrides.mask_feathering if overrides else 4,
        temporal_smoothing=overrides.temporal_smoothing if overrides else False,
        output_resolution=overrides.output_resolution if overrides else None,
        preserve_audio=overrides.preserve_audio if overrides else True,
    )
    job = proc_repo.create_job(db, p, job_type=JobType.process, quality_mode=quality)
    # created -> processing_queued (legal under _TRANSITIONS).
    proc_repo.transition(db, job, JobState.processing_queued, stage="queued")
    p.status = ProjectStatus.processing_queued
    db.commit()
    db.refresh(job)

    # Enqueue on the processing queue. Imported lazily so the API process does
    # not require Celery to import (unit tests reach the route helpers
    # directly without a running broker).
    # Importing workers.celery_app FIRST makes it the current Celery app, so the
    # @shared_task `process_video` binds to it (broker_url, queues, pool settings).
    # Without this, shared_task binds to Celery's default app, whose broker_url is
    # None — apply_async raises kombu OperationalError "connection refused" and
    # /process returns 500, leaving the job stuck at processing_queued (UI shows
    # "queued · 0% (0/0 frames)" forever).
    import workers.celery_app  # noqa: F401 — current-app setup
    from workers.tasks.processing import process_video

    process_video.apply_async(args=(job.id, p.id), queue="processing")

    return ProcessResponse(job_id=job.id, project_id=p.id, status=job.status.value)


@project_router.get("/{project_id}/jobs", response_model=list[JobStatusResponse])
def list_project_jobs(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobStatusResponse]:
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    jobs = proc_repo.list_jobs_for_project(db, p.id)
    return [JobStatusResponse.model_validate(j) for j in jobs]


@jobs_router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobStatusResponse:
    job = proc_repo.get_job_owned(db, job_id, user.id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)
    return JobStatusResponse.model_validate(job)


@jobs_router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    job = proc_repo.get_job_owned(db, job_id, user.id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)

    async def gen() -> AsyncIterator[bytes]:
        import redis as _redis_mod

        r = _redis_mod.from_url(settings.redis_url)
        key = f"job_events:{job_id}"

        # Replay any history already written, then tail.
        backlog = r.lrange(key, 0, -1) or []
        if not backlog:
            # No events yet — emit a synthetic "waiting" tick so the client
            # knows the stream is open before the worker publishes.
            yield _sse_frame({"stage": "queue", "progress": job.progress, "frames_processed": 0,
                              "total_frames": job.total_frames, "warnings": [],
                              "message": "Waiting for worker.", "terminal": False})
        for raw in backlog:
            yield _sse_frame(json.loads(raw))
            data = json.loads(raw)
            if data.get("terminal"):
                return

        # Tail until terminal or client disconnect.
        terminal = any(json.loads(raw).get("terminal") for raw in (backlog or []))
        while not terminal:
            if await request.is_disconnected():
                return
            packed = r.brpop(key, timeout=15)
            if packed is None:
                # keep-alive comment so proxies don't drop idle connections.
                yield b": keep-alive\n\n"
                continue
            payload = json.loads(packed[1])
            yield _sse_frame(payload)
            if payload.get("terminal"):
                return

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _sse_frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


__all__ = ["project_router", "jobs_router"]
