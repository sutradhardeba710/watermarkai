"""Phase 7 detection Celery task (SRS DETECT-001..007, AI-001/002/004/006,
PROCESS, WORKER).

Pipeline:
    created -> analyzing -> awaiting_review -> (cancelled on no-candidates)
    success -> project.status = awaiting_review, candidates persisted

Stages:
    1. Acquire per-job Redis lock (same Phase 5 pattern).
    2. Download the original video to an isolated tempdir (WORKER-005).
    3. Sample frames at sample_fps via FFmpeg (FRAME-001) into PGM/PNG files.
    4. Build a FrameSource for the orchestrator and run pipeline.run_detection.
    5. Persist each RankedCandidate as a WatermarkCandidate row (DETECT-002).
    6. Update project.status to awaiting_review; emit a terminal SSE event.

The actual detection stages (YOLO, OCR) live behind their own heavy-import
interfaces so this task imports cleanly on a 32-bit box. The 64-bit worker
process is where the inference actually runs.

Progress is published to ``job_events:{job_id}`` so the Phase 5 SSE endpoint
already in place streams liveness to the client — no parallel SSE machinery.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from celery import shared_task

import workers.ai_models_paths  # noqa: F401 — alias ai_models / ai_model_interfaces
import workers.tasks.processing as proc_task  # reuse publish_event / _event
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models import (
    JobState,
    ProjectStatus,
    VideoProject,
)
from app.repositories import candidates as cand_repo
from app.repositories import processing as proc_repo
from app.services.frame_sample import sample_timestamps
from app.storage.factory import get_storage
from workers.common import isolated_tempdir, job_lock

settings = get_settings()
ORIGINAL_BUCKET = "originals"
FRAMES_DIR_NAME = "frames_detect"

# Detectors to run by default. Late-bound on the 64-bit worker so this module
# imports clean on a 32-bit box (no ultralytics / easyocr wheels available).
DEFAULT_DETECTOR_NAMES = ("heuristic", "yolo", "ocr")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redis():
    import redis

    return redis.from_url(settings.redis_url)


def _download_original(project: VideoProject, dest: Path) -> Path:
    storage = get_storage()
    key = project.input_storage_key or (project.id + "/" + project.original_filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(storage.download_to_file(ORIGINAL_BUCKET, key, str(dest)))


def _extract_sample_frames(src: Path, out_dir: Path, timestamps: list[float]) -> list[Path]:
    """Pull the requested sample timestamps as PNG files via FFmpeg's
    ``-vf select='eq(n,K)'`` filter. Returns the sorted file list. Falls back
    to a single-frame probe when nothing was requested (defensive)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    if not timestamps:
        return paths
    import cv2  # heavy; deferred

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    written = 0
    for idx, t in enumerate(timestamps):
        target = int(round(t * fps))
        if target >= frame_count and frame_count > 0:
            target = max(0, frame_count - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        fp = out_dir / f"frame_{idx:04d}.png"
        cv2.imwrite(str(fp), frame)
        paths.append(fp)
        written += 1
    cap.release()
    return paths


def _candidate_dict_from_ranked(rc) -> dict[str, Any]:
    """Convert a RankedCandidate to the storage row shape."""
    bb = rc.bbox
    return {
        "candidate_type": _candidate_type_for_source(rc.source),
        "confidence": float(rc.confidence_score),
        "bounding_box": {"x": bb[0], "y": bb[1], "w": bb[2], "h": bb[3]},
        "is_static": True,
        "tracking_data": {"signals": rc.detector_signals.__dict__,
                          "source": rc.source,
                          "text": rc.text,
                          "label": rc.confidence_label},
    }


def _candidate_type_for_source(source: str) -> str:
    return {"yolo": "logo", "ocr": "text", "heuristic": "logo",
            "merged": "logo"}.get(source, "logo")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_detection_pipeline(job_id: str, project_id: str,
                            *, dry_run_path: str | None = None) -> None:
    """Drives the full detection job. Mirrors ``run_pipeline`` in Phase 5 with the
    detection-shaped state transitions so the existing SSE machinery streams
    progress without changes."""
    wid = f"detector-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        job = proc_repo.get_job(db, job_id)
        if job is None:
            return
        project = db.get(VideoProject, project_id)
        if project is None:
            proc_repo.mark_failed(db, job, "PROJECT_MISSING", "Project not found.")
            db.commit()
            proc_task.publish_event(job_id, proc_task._event(
                "failed", 100, terminal=True,
                error_code="PROJECT_MISSING", message="Project not found."))
            return

        # created -> processing_queued -> analyzing
        proc_repo.transition(db, job, JobState.processing_queued, stage="queued")
        db.commit()

        with job_lock(job_id, wid, ttl_seconds=settings.job_timeout_seconds) as got:
            if not got:
                proc_repo.mark_failed(db, job, "LOCK_BUSY",
                                      "Another worker is already processing this job.")
                db.commit()
                proc_task.publish_event(job_id, proc_task._event(
                    "failed", 100, terminal=True,
                    error_code="LOCK_BUSY",
                    message="Job already held by another worker."))
                return
            _execute_detection(db, job, project, wid,
                               dry_run_path=dry_run_path)
    finally:
        db.close()


def _execute_detection(db, job, project, wid: str, *,
                       dry_run_path: str | None) -> None:
    job_id = job.id
    project_id = project.id
    try:
        proc_repo.transition(db, job, JobState.analyzing, stage="sample")
        db.commit()
        proc_task.publish_event(job_id, proc_task._event(
            "sample", 2, message="Sampling frames for detection."))

        # idempotent reanalysis — wipe prior candidates so the user's view is the latest run
        cand_repo.clear_candidates_for(db, project_id)

        duration = float(project.duration or 0.0)
        timestamps = sample_timestamps(duration, sample_fps=1.0, min_samples=10)
        if not timestamps:
            # tiny clips / metadata gap — fall back to one middle-of-clip timestamp
            timestamps = [duration / 2] if duration > 0 else []

        with isolated_tempdir(prefix=f"vwa-detect-{job_id}-") as work:
            src_path = (Path(dry_run_path) if dry_run_path
                        else _download_original(
                            project, work / "source" / project.original_filename))

            frames_dir = work / FRAMES_DIR_NAME
            frame_paths = _extract_sample_frames(src_path, frames_dir, timestamps)
            if not frame_paths:
                raise AppError("EXTRACT_FAILED",
                               "Could not sample any frames from the uploaded video.",
                               502)

            proc_repo.set_progress(db, job, 25, total_frames=len(frame_paths),
                                  frames_processed=0, stage="sampling")
            db.commit()
            proc_task.publish_event(job_id, proc_task._event(
                "sample", 25, total_frames=len(frame_paths),
                frames_processed=0,
                message=f"Sampled {len(frame_paths)} frames."))

            # Stage orchestration
            proc_repo.transition(db, job, JobState.analyzing, stage="heuristic")
            db.commit()
            proc_task.publish_event(job_id, proc_task._event("heuristic", 35,
                                                            message="Running heuristic pre-screen."))

            # import orchestrator + detectors (deferred heavy)
            from ai_models.detection.heuristic_prescreen import (
                prescreen_frames, top_rois, signals_from_roi,
            )
            from ai_models.detection.pipeline import (
                DetectionConfig, DetectionReport, fuse_stage_candidates,
                run_detection,
            )

            cfg = DetectionConfig(sample_fps=1.0)

            # Build a frame_source from the sampled PNGs (no cv2 required)
            import cv2  # heavy
            import numpy as np  # heavy

            frames_list: list[tuple[int, Any]] = []
            for i, fp in enumerate(frame_paths):
                encoded = np.fromfile(str(fp), dtype=np.uint8)
                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if frame is not None:
                    frames_list.append((i, frame))
            if not frames_list:
                raise AppError(
                    "EXTRACT_FAILED",
                    "Could not decode any sampled frames for detection.",
                    502,
                )

            report: DetectionReport = run_detection(
                duration_seconds=duration,
                frame_source=lambda: frames_list,
                ocr_provider=None,
                cfg=cfg,
            )

            # Stage 2 — YOLO. Injected here so the worker process owns the
            # heavy dep lifecycle.
            yolo_candidates: list = []
            if "yolo" in DEFAULT_DETECTOR_NAMES:
                try:
                    from ai_models.detection.yolo_logo_detector import YoloLogoDetector
                    yolo = YoloLogoDetector()
                    yolo_report = yolo.detect(str(src_path), duration,
                                              sample_fps=cfg.sample_fps)
                    yolo_candidates = yolo_report.candidates
                except Exception as exc:  # noqa: BLE001 — AGPL weights absent, etc.
                    # Record the warning but continue — Stage 1+3 may still
                    # surface a useful manual-flag candidate.
                    proc_task.publish_event(job_id, proc_task._event(
                        "yolo", 50, warnings=[f"yolo unavailable: {exc!r}"]))

            # Re-fuse to include the YOLO candidates alongside heuristic+OCR.
            heur_rois = top_rois(
                prescreen_frames([f for _, f in frames_list],
                                 frame_w=int(project.width or 0),
                                 frame_h=int(project.height or 0)),
                k=cfg.max_heuristic_rois, min_score=cfg.min_roi_score,
            )
            ranked = fuse_stage_candidates(heur_rois, yolo_candidates,
                                           report.ranked and [c for c in report.ranked
                                                if c.source == "ocr"] or [],
                                           cfg)
            reliable = [
                candidate for candidate in ranked
                if not candidate.needs_manual_selection
            ]

            proc_repo.transition(db, job, JobState.analyzing, stage="rank")
            db.commit()
            proc_task.publish_event(job_id, proc_task._event(
                "rank", 80,
                total_frames=len(timestamps),
                message=f"Picked {len(reliable)} reliable candidates."))

            # Persist candidates
            for rc in reliable:
                row = _candidate_dict_from_ranked(rc)
                cand_repo.create_candidate(
                    db,
                    project_id=project_id,
                    user_id=project.user_id,
                    candidate_type=row["candidate_type"],
                    confidence=row["confidence"],
                    bounding_box=row["bounding_box"],
                    is_static=True,
                    tracking_data=row["tracking_data"],
                )

            # Decide the next project state. DETECT-006: an empty candidate list
            # still routes the project to awaiting_review — the frontend reads
            # the candidate list and shows "manual selection required" when
            # it's empty. Avoiding a new enum value here keeps the migration
            # surface unchanged.
            project.status = ProjectStatus.awaiting_review
            db.commit()

            proc_repo.set_progress(
                db,
                job,
                100,
                frames_processed=len(frame_paths),
                total_frames=len(frame_paths),
                stage="awaiting_review",
            )
            proc_repo.transition(db, job, JobState.completed, stage="awaiting_review")
            db.commit()
            proc_task.publish_event(job_id, proc_task._event(
                "completed", 100, terminal=True,
                message=f"Analysis complete: {len(reliable)} candidates."))

    except AppError as exc:
        _fail(db, job, project, exc.code, exc.message, stage=job.current_stage)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - FFmpeg failures
        _fail(db, job, project, "FFMPEG_ERROR", f"ffmpeg exited {exc.returncode}")
    except Exception as exc:  # noqa: BLE001 — surface any failure on the job
        _fail(db, job, project, "INTERNAL", repr(exc))


def _fail(db, job, project, code: str, msg: str, *, stage: str | None = None) -> None:
    try:
        proc_repo.mark_failed(db, job, code, msg, stage=stage)
        project.status = ProjectStatus.failed
        db.commit()
    except Exception:
        db.rollback()
    proc_task.publish_event(job.id, proc_task._event(
        "failed", 100, terminal=True,
        error_code=code, message=msg))


# ---------------------------------------------------------------------------
# Celery binding
# ---------------------------------------------------------------------------


@shared_task(name="workers.tasks.detection.analyze_video", bind=True,
             max_retries=settings.max_retries, queue="detection")
def analyze_video(self, job_id: str, project_id: str,
                  dry_run_path: str | None = None) -> None:
    """Entry point. Acquires the lock via :func:`run_detection_pipeline` and
    reports progress via the shared SSE machinery."""
    try:
        run_detection_pipeline(job_id, project_id, dry_run_path=dry_run_path)
    except Exception as exc:  # noqa: BLE001 — final safety net
        # The DB row is already marked failed in run_detection_pipeline.
        raise self.retry(exc=exc, countdown=2 * (self.request.retries + 1))


__all__ = ["analyze_video", "run_detection_pipeline"]
