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
from app.services.compliance import gate_processing_allowed, gate_unconfirmed
from app.services.payment_service import deduct_credits, refund_credits, CREDITS_PER_JOB
from app.services.task_dispatch import BrokerUnavailable, dispatch_task

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


def _process_image_direct(project: VideoProject, mask, quality: str) -> str:
    """In-process full-resolution inpainting for an image project."""
    import shutil
    import tempfile
    from pathlib import Path
    import cv2
    from app.api.preview import StaticMaskForPreview, _new_inpainter
    from app.services.validation import file_extension
    from app.storage.factory import get_storage

    storage = get_storage()
    src_bucket = "originals" if project.input_storage_key else "proxies"
    src_key = project.input_storage_key or project.proxy_storage_key
    if not src_key:
        raise AppError("SOURCE_MISSING", "Original image not found in storage.", 404)

    ext = file_extension(project.original_filename)
    ext = ext if ext in ("png", "jpg", "jpeg", "webp") else "png"

    work_dir = Path(tempfile.mkdtemp(prefix="vwa-img-proc-"))
    try:
        local_src = work_dir / f"original.{ext}"
        storage.download_to_file(src_bucket, src_key, str(local_src))

        frame = cv2.imread(str(local_src), cv2.IMREAD_COLOR)
        if frame is None:
            raise AppError("PROCESSING_FAILED", "Could not decode source image.", 502)

        h, w = frame.shape[:2]
        cache = StaticMaskForPreview(mask, int(project.width or w), int(project.height or h))
        mask_u8 = cache.get_for(w, h)

        inpainter = _new_inpainter()
        cleaned = inpainter.inpaint_frame(frame, mask_u8, quality=quality)

        out_file = work_dir / f"clean.{ext}"
        cv2.imwrite(str(out_file), cleaned)

        out_key = f"{project.id}/clean.{ext}"
        mime = "image/png" if ext == "png" else "image/webp" if ext == "webp" else "image/jpeg"
        storage.put_file("outputs", out_key, str(out_file), content_type=mime)
        return out_key
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# A created/processing_queued job older than this with no worker ever having
# started it is treated as dead — its Celery message is no longer in the queue
# (worker was down at enqueue time, or died mid-flight without acking), so
# returning it would permanently block the idempotent enqueue path and leave
# the UI stuck on "queued · 0% (0/0 frames)".
_STALE_QUEUE_SECONDS = 300


def _active_job(db: Session, project_id: str, user: User):
    """A genuinely-active *process* job already attached to this project.

    `processing`/`encoding` jobs are always considered active (a worker owns
    them). A `created`/`processing_queued` job is active while it is younger
    than the stale window (queued jobs never have `started_at`, so age is
    measured from `created_at`). Older ones are treated as dead — the Celery
    message was lost — and are cancelled *with a credit refund* so a fresh
    Approve can enqueue without double-charging.

    Analyze jobs are ignored: they share the jobs table but never cost
    credits, and returning one here would make /process report a detection
    job as the process job (and refunding a stale one would mint credits the
    user never spent).
    """
    jobs = proc_repo.list_jobs_for_project(db, project_id)
    now = datetime.now(timezone.utc)
    for j in jobs:
        if j.job_type != JobType.process:
            continue
        if j.status in (JobState.processing, JobState.encoding):
            return j
        if j.status in (JobState.created, JobState.processing_queued):
            created = j.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created is not None and (now - created) < timedelta(seconds=_STALE_QUEUE_SECONDS):
                return j
            # Stale: no worker picked it up within the window. Cancel and
            # refund so the caller can enqueue a fresh job without paying twice.
            proc_repo.transition(
                db, j, JobState.cancelled,
                stage=j.current_stage,
                error_code="STALE_QUEUED",
                error_message="Enqueued but never picked up by a worker; re-approve to retry.",
            )
            refund_credits(db, user=user, cost=CREDITS_PER_JOB)
            db.commit()
    return None


@project_router.post("/{project_id}/process", response_model=ProcessResponse)
def enqueue_process(
    project_id: str,
    body: ProcessRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProcessResponse:
    p = _owned_ready_project(db, project_id, user)

    # LEGAL-003: gate behind ownership confirmation.
    gate_unconfirmed(upload_repo.has_confirmation(db, p.id))
    # PRD §9.5: moderation flags (locked / restricted / legal hold) block processing.
    gate_processing_allowed(p)
    _require_mask(db, p.id)

    # Idempotent: one active job per project.
    existing = _active_job(db, p.id, user)
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

    from app.services.validation import file_extension, IMAGE_EXTENSIONS
    is_image = file_extension(p.original_filename) in IMAGE_EXTENSIONS or (
        p.frame_count == 1 and (p.duration or 0.0) == 0.0
    )

    if is_image:
        image_cost = 1
        deduct_credits(db, user=user, cost=image_cost)
        job = proc_repo.create_job(db, p, job_type=JobType.process, quality_mode=quality)
        proc_repo.transition(db, job, JobState.processing, stage="inpainting")
        p.status = ProjectStatus.processing
        db.commit()

        try:
            out_key = _process_image_direct(p, mask, quality.value)
            p.output_storage_key = out_key
            p.status = ProjectStatus.completed
            proc_repo.transition(db, job, JobState.completed, stage="done")
            job.progress = 100
            db.commit()
            return ProcessResponse(job_id=job.id, project_id=p.id, status=job.status.value)
        except Exception as exc:
            refund_credits(db, user=user, cost=image_cost)
            proc_repo.transition(
                db, job, JobState.failed, stage="inpainting",
                error_code="PROCESSING_FAILED",
                error_message=f"Image inpainting failed: {exc}",
            )
            p.status = ProjectStatus.failed
            db.commit()
            raise AppError("PROCESSING_FAILED", f"Image processing failed: {exc}", 502) from exc

    # BILLING: deduct credits before dispatching. Raises 402 if balance is low.
    deduct_credits(db, user=user, cost=CREDITS_PER_JOB)

    job = proc_repo.create_job(db, p, job_type=JobType.process, quality_mode=quality)
    # created -> processing_queued (legal under _TRANSITIONS).
    proc_repo.transition(db, job, JobState.processing_queued, stage="queued")
    p.status = ProjectStatus.processing_queued
    db.commit()
    db.refresh(job)

    # Enqueue on the processing queue. Publishing is delegated to dispatch_task,
    # which imports the Celery app lazily (so unit tests can reach the route
    # helpers without a running broker), retries once on a fresh connection to
    # survive a stale pooled socket (the common Windows/OneDrive case), and logs
    # the real error instead of masking every failure as "broker unavailable".
    try:
        from workers.tasks.processing import process_video
        dispatch_task(process_video, args=(job.id, p.id), queue="processing")
    except BrokerUnavailable:
        # Broker is genuinely unreachable — refund credits and surface a useful
        # error rather than leaving the user charged with a stuck job.
        refund_credits(db, user=user, cost=CREDITS_PER_JOB)
        proc_repo.transition(db, job, JobState.failed, stage="dispatch",
                             error_code="BROKER_UNAVAILABLE",
                             error_message="Could not enqueue job: Celery broker unavailable.")
        db.commit()
        raise AppError("BROKER_UNAVAILABLE", "Processing queue is not available. Please try again shortly.", 503)

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

        # Replay any history already written, then tail. Reads are
        # non-destructive (LRANGE from a moving cursor) so events arrive
        # oldest-first, reconnects/second clients still see the full sequence,
        # and the sync redis client is only ever called via a worker thread —
        # BRPOP here would block the whole event loop for its timeout *and*
        # pop newest-first, delivering the terminal event before the progress
        # events it should follow.
        backlog = await asyncio.to_thread(r.lrange, key, 0, -1) or []
        if not backlog:
            # No events yet — emit a synthetic "waiting" tick so the client
            # knows the stream is open before the worker publishes.
            yield _sse_frame({"stage": "queue", "progress": job.progress, "frames_processed": 0,
                              "total_frames": job.total_frames, "warnings": [],
                              "message": "Waiting for worker.", "terminal": False})
        offset = len(backlog)
        for raw in backlog:
            payload = json.loads(raw)
            yield _sse_frame(payload)
            if payload.get("terminal"):
                return

        # Tail until terminal or client disconnect.
        idle_seconds = 0.0
        while True:
            if await request.is_disconnected():
                return
            fresh = await asyncio.to_thread(r.lrange, key, offset, -1) or []
            if not fresh:
                await asyncio.sleep(1.0)
                idle_seconds += 1.0
                if idle_seconds >= 15.0:
                    # keep-alive comment so proxies don't drop idle connections.
                    yield b": keep-alive\n\n"
                    idle_seconds = 0.0
                continue
            idle_seconds = 0.0
            offset += len(fresh)
            for raw in fresh:
                payload = json.loads(raw)
                yield _sse_frame(payload)
                if payload.get("terminal"):
                    return

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _sse_frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


__all__ = ["project_router", "jobs_router"]
