"""Phase 5 processing task — inpaint + encode (SRS RECON, ENCODE, PROCESS, WORKER, REL).

Pipeline:
  created -> processing_queued -> processing -> encoding -> completed
  (failure at any step -> failed; PROJECT-002 recorded on the VideoProject)

Stages:
  1. Acquire per-job Redis lock (WORKER-004), stamp worker_id + heartbeat.
  2. Download original + remux original audio to an isolated tempdir (WORKER-005).
  3. Extract every frame to PNG (no re-encode) at the source FPS.
  4. Build the static inpaint mask once (MASK-005 / MASK-004 morphology).
  5. Per-frame `cv2.inpaint` via OpenCVInpainter (Fast/Balanced/High). High mode
     blends with the previous frame (TEMP-001).
  6. Encode frames + remuxed audio to H.264 yuv420p (ENCODE-001..004).
  7. ffprobe-validate the output (ENCODE-007) and persist an OutputFile.
  8. Mark the project completed; clean up frames immediately (WORKER-005).

Progress is published to a Redis list `job_events:{job_id}` (RPUSH) and expiring
so the SSE endpoint (:mod:`app.api.processing`) can poll it without sharing
memory with the worker.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from celery import shared_task

import workers.ai_models_paths  # noqa: F401 — alias ai_models / ai_model_interfaces
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models import JobState, QualityMode, User, VideoProject, WatermarkMask
from app.repositories import processing as proc_repo
from app.repositories import uploads as upload_repo
from app.services import encode as encode_svc
from app.services import normalize
from app.services.mask_render import StaticMaskCache
from app.storage.factory import get_storage
from workers.common import LockBusy, isolated_tempdir, job_lock

settings = get_settings()
ORIGINAL_BUCKET = "originals"
FRAMES_DIR_NAME = "frames"
AUDIO_NAME = "original_audio.aac"
INPAINTED_DIR_NAME = "inpainted"
OUTPUT_NAME = "output.mp4"


# ---------------------------------------------------------------------------
# Progress publishing (read by the SSE endpoint)
# ---------------------------------------------------------------------------


_redis_client = None


def _redis():
    """Cached module-level client — publish_event runs once per frame, and a
    fresh connection per call means one TCP handshake per frame."""
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


def publish_event(job_id: str, event: dict[str, Any]) -> None:
    """RPUSH the event JSON to `job_events:{job_id}` and set a short TTL.

    The SSE endpoint BRPOP from this list and emits `data:` lines. A TTL keeps
    the key from leaking if the client disconnects before draining.
    """
    r = _redis()
    key = f"job_events:{job_id}"
    r.rpush(key, json.dumps(event))
    r.expire(key, 3600)


def _event(stage: str, progress: int, **fields) -> dict[str, Any]:
    payload = {"stage": stage, "progress": int(progress)}
    payload.update(fields)
    return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ls_frames(frames_dir: Path) -> list[Path]:
    return sorted(frames_dir.glob("frame_*.png"))


def _download_original(project: VideoProject, dest: Path) -> Path:
    storage = get_storage()
    key = project.input_storage_key or (project.id + "/" + project.original_filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(storage.download_to_file(ORIGINAL_BUCKET, key, str(dest)))


def _quality_from(mode: QualityMode) -> str:
    return {"fast": "fast", "balanced": "balanced", "high": "high"}.get(mode.value, "balanced")


def _resolve_mask_for(project: VideoProject, mask: WatermarkMask):
    """Build the static inpaint mask, projecting the stored geometry onto the
    project's real source frame size (the mask was validated against it)."""
    cache = StaticMaskCache(
        mask.tool,
        mask.geometry,
        int(project.width),
        int(project.height),
        mask_expansion=mask.mask_expansion,
        mask_feathering=mask.mask_feathering,
    )
    return cache.get()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(job_id: str, project_id: str, *, dry_run_path: str | None = None) -> None:
    """Execute the full processing/encode pipeline and update DB + events.

    ``dry_run_path`` (tests only) skips the actual source download and inpaints
    against the file at this path. Heavy deps (cv2, numpy) are imported inside
    the steps that need them so importing the module stays light.
    """
    wid = f"worker-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        job = proc_repo.get_job(db, job_id)
        if job is None:
            return
        project = db.get(VideoProject, project_id)
        if project is None:
            proc_repo.mark_failed(db, job, "PROJECT_MISSING", "Project not found.")
            db.commit()
            publish_event(job_id, _event("failed", 100, terminal=True,
                                         error_code="PROJECT_MISSING", message="Project not found."))
            return
        mask = upload_repo.latest_mask(db, project_id)
        if mask is None:
            proc_repo.mark_failed(db, job, "MASK_MISSING", "No mask saved for project.")
            db.commit()
            publish_event(job_id, _event("failed", 100, terminal=True,
                                         error_code="MASK_MISSING", message="No mask saved."))
            return

        # The job is already `processing_queued` — the /process route set it
        # there before dispatching. The real queued -> processing move happens
        # inside _execute_job under the lock (stage="extract").
        #
        # We must NOT re-transition to processing_queued here: with
        # task_acks_late=True, a worker that dies/reloads mid-job has its message
        # redelivered while the DB row is still `processing`. Trying to move
        # processing -> processing_queued then raises "illegal job transition"
        # and the task crash-loops through every retry, leaving the UI stuck on
        # "Queued · 0%". Guard terminal states instead so redelivery is a clean
        # no-op rather than a reprocess.
        if job.status in (JobState.completed, JobState.failed, JobState.cancelled, JobState.expired):
            return

        with job_lock(job_id, wid, ttl_seconds=settings.job_timeout_seconds) as got:
            if not got:
                # Another worker holds the lock — or a crashed worker left a
                # stale one behind (its TTL will expire). Don't fail the job:
                # with acks-late redelivery the retry either finds the other
                # worker finished it (terminal guard above) or acquires the
                # lock once the TTL lapses.
                raise LockBusy(job_id)
            _execute_job(db, job, project, mask, wid, dry_run_path=dry_run_path)
    finally:
        db.close()


def _execute_job(db, job, project, mask, wid: str, *, dry_run_path: str | None) -> None:
    job_id = job.id
    try:
        proc_repo.transition(db, job, JobState.processing, stage="extract")
        db.commit()
        publish_event(job_id, _event("extract", 2, message="Extracting frames."))

        with isolated_tempdir(prefix=f"vwa-job-{job_id}-") as work:
            # Original local copy
            src_path = Path(dry_run_path) if dry_run_path else _download_original(
                project, work / "source" / project.original_filename
            )

            # Audio demux (may fail quietly when the source has no audio)
            audio_path = work / AUDIO_NAME
            has_audio = _try_remux_audio(src_path, audio_path)

            # Frame extraction. Extract and encode must use the SAME rate: if
            # project.fps is unknown, extracting at native rate but encoding at
            # the 25fps fallback stretches/shrinks the output and fails the
            # ±100ms duration validation.
            fps = float(project.fps or 25.0)
            frames_dir = work / FRAMES_DIR_NAME
            frames_dir.mkdir(parents=True, exist_ok=True)
            normalize.run_ffmpeg(
                encode_svc.extract_frames_args(src_path, frames_dir, fps=fps)
            )
            frame_paths = _ls_frames(frames_dir)
            total = len(frame_paths)
            if total == 0:
                raise AppError("EXTRACT_FAILED", "FFmpeg produced no frames.", 502)
            job.total_frames = total
            db.commit()

            publish_event(job_id, _event("extract", 5, total_frames=total,
                                         message=f"Extracted {total} frames."))

            # Inpaint
            proc_repo.transition(db, job, JobState.processing, stage="inpaint")
            db.commit()
            publish_event(job_id, _event("inpaint", 8))
            mask_u8 = _resolve_mask_for(project, mask)
            inpainted_dir = work / INPAINTED_DIR_NAME
            inpainted_dir.mkdir(parents=True, exist_ok=True)
            _inpaint_all(db, job_id, job, project, frame_paths, mask_u8, inpainted_dir)

            # Encode
            proc_repo.transition(db, job, JobState.encoding, stage="encode")
            db.commit()
            publish_event(job_id, _event("encode", 92, message="Encoding."))

            out_local = work / OUTPUT_NAME
            audio_codec = "copy"
            audio_arg = audio_path if has_audio else None
            normalize.run_ffmpeg(
                encode_svc.encode_args(
                    inpainted_dir,
                    out_local,
                    fps=fps,
                    audio_path=audio_arg,
                    audio_codec=audio_codec,
                    output_codec=settings.output_codec,
                    pixel_format=settings.output_pixel_format,
                )
            )

            # Validate
            meta = _validate_output(out_local)
            if not meta["has_video"]:
                raise AppError("ENCODE_FAILED", "Output has no video stream.", 502)
            if not encode_svc.output_duration_within_tolerance(
                project.duration, meta["duration"]
            ):
                raise AppError(
                    "ENCODE_FAILED",
                    f"Output duration {meta['duration']}s diverges from source "
                    f"{project.duration}s.",
                    502,
                )

            # Persist to storage + DB
            out_key = f"{project.id}/{OUTPUT_NAME}"
            storage = get_storage()
            storage.put_file("outputs", out_key, str(out_local), content_type="video/mp4")

            proc_repo.record_output(
                db, project, out_key,
                duration=meta["duration"],
                width=meta["width"],
                height=meta["height"],
                file_size=out_local.stat().st_size,
                quality_mode=job.processing_mode,
            )
            proc_repo.complete_project(db, project, out_key)
            proc_repo.transition(db, job, JobState.completed, stage="completed")
            db.commit()
            publish_event(job_id, _event("completed", 100, terminal=True,
                                         message="Processing complete."))

    except AppError as exc:
        _fail(db, job, project, exc.code, exc.message, stage=job.current_stage)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        _fail(db, job, project, "FFMPEG_ERROR", f"ffmpeg exited {exc.returncode}")
    except Exception as exc:  # noqa: BLE001 — surface any failure on the job
        _fail(db, job, project, "INTERNAL", repr(exc))


def _inpaint_all(db, job_id, job, project, frame_paths, mask_u8, out_dir) -> None:
    import cv2  # noqa: WPS433 - heavy dep, imported lazily

    inpainter = _new_inpainter()
    quality = _quality_from(job.processing_mode)
    total = len(frame_paths)
    prev_out = None
    for idx, fp in enumerate(frame_paths):
        frame = cv2.imread(str(fp), cv2.IMREAD_COLOR)
        if frame is None:
            # Copy the original frame through so the numbered sequence has no
            # gap — the image2 demuxer stops at the first missing index, which
            # would truncate the output and fail the duration validation.
            publish_event(job_id, _event("inpaint", job.progress,
                                         warnings=[f"unreadable frame {fp.name}"]))
            shutil.copyfile(str(fp), str(out_dir / fp.name))
            continue
        if mask_u8.shape[:2] != frame.shape[:2]:
            mask_u8 = cv2.resize(mask_u8, (frame.shape[1], frame.shape[0]),
                                 interpolation=cv2.INTER_NEAREST)
        out = inpainter.inpaint_frame(frame, mask_u8, previous_frame=prev_out, quality=quality)
        cv2.imwrite(str(out_dir / fp.name), out)
        prev_out = out if quality == "high" else prev_out
        done = idx + 1
        # inpaint covers the 8%..90% band of overall progress
        pct = 8 + int((done / total) * 82)
        proc_repo.set_progress(db, job, pct, frames_processed=done,
                               total_frames=total, stage="inpaint")
        db.commit()
        publish_event(job_id, _event("inpaint", pct, frames_processed=done,
                                     total_frames=total))
    proc_repo.set_progress(db, job, 90, frames_processed=total,
                           total_frames=total, stage="encode")
    db.commit()


def _new_inpainter():
    from ai_models.inpainting.opencv_inpainter import OpenCVInpainter

    return OpenCVInpainter()


def _try_remux_audio(src: Path, dst_audio: Path) -> bool:
    """Extract the source audio for the final mux (ENCODE-004).

    Try a lossless stream copy first (AAC sources); when the codec can't live
    in the .aac container (webm Vorbis/Opus, MOV PCM) fall back to an AAC
    re-encode instead of silently dropping the track. Only when both fail do
    we treat the source as having no usable audio.
    """
    try:
        normalize.run_ffmpeg(encode_svc.remux_audio_args(src, dst_audio))
        if dst_audio.exists() and dst_audio.stat().st_size > 0:
            return True
    except AppError:
        pass
    try:
        normalize.run_ffmpeg(encode_svc.transcode_audio_aac_args(src, dst_audio))
        return dst_audio.exists() and dst_audio.stat().st_size > 0
    except AppError:
        # genuinely no audio stream — mux without audio
        return False


def _validate_output(path: Path) -> dict:
    from app.services.validation import probe_container

    meta = probe_container(str(path))
    return {
        "duration": meta.get("duration"),
        "width": meta.get("width"),
        "height": meta.get("height"),
        "has_video": bool(meta.get("video_codec")),
    }


def _fail(db, job, project, code: str, msg: str, *, stage: str | None = None) -> None:
    already_terminal = job.status in (
        JobState.completed, JobState.failed, JobState.cancelled, JobState.expired
    )
    proc_repo.mark_failed(db, job, code, msg, stage=stage)
    proc_repo.fail_project(db, project)
    if not already_terminal:
        _refund_job_credits(db, job)
    db.commit()
    publish_event(job.id, _event("failed", 100, terminal=True,
                                 error_code=code, message=msg))


def _refund_job_credits(db, job) -> None:
    """The user was charged at enqueue time and nothing was delivered — return
    the credits. At most one refund per job (admin retries don't re-charge, so
    a second failure must not mint a second refund). Best-effort: a refund
    problem must never mask the underlying job failure."""
    try:
        from app.models import CreditTransaction
        from app.services.payment_service import CREDITS_PER_JOB, refund_credits

        already = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.job_id == job.id, CreditTransaction.source == "refund")
            .first()
        )
        if already is not None:
            return
        user = db.get(User, job.user_id)
        if user is not None:
            refund_credits(db, user=user, cost=CREDITS_PER_JOB,
                           project_id=job.project_id, job_id=job.id)
    except Exception:  # noqa: BLE001 — never let the refund break the failure path
        pass


# ---------------------------------------------------------------------------
# Celery binding
# ---------------------------------------------------------------------------


@shared_task(name="workers.tasks.processing.process_video", bind=True,
             max_retries=settings.max_retries, queue="processing")
def process_video(self, job_id: str, project_id: str, dry_run_path: str | None = None) -> None:
    """Entry point. Acquires the lock via :func:`run_pipeline` and reports
    retries/terminal state back to Celery."""
    try:
        run_pipeline(job_id, project_id, dry_run_path=dry_run_path)
    except LockBusy as exc:
        # Someone else owns the job right now (or a crashed worker's stale
        # lock is waiting out its TTL). Retry later rather than failing.
        raise self.retry(exc=exc, countdown=120)
    except Exception as exc:  # noqa: BLE001 — final safety net; pipeline handles its own failures
        # The DB row is already marked failed in run_pipeline; bubble the retry.
        raise self.retry(exc=exc, countdown=2 * (self.request.retries + 1))


__all__ = ["process_video", "publish_event", "run_pipeline"]
