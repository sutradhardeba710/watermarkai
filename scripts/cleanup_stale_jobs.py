"""One-off: cancel stale queued/created processing jobs that no worker ever
picked up (started_at is None and a Celery message is no longer in the queue).

These rows otherwise permanently block the idempotent `enqueue_process` path
(`_active_job` short-circuits on them), so the UI shows "queued · 0% (0/0
frames)" forever and Approve never re-enqueues.

Run once from the repo root:
    backend/.venv/Scripts/python.exe scripts/cleanup_stale_jobs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.models import JobState, ProcessingJob, ProjectStatus, VideoProject  # noqa: E402
from app.repositories import processing as proc_repo  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        stale = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.status.in_(
                    [JobState.created, JobState.processing_queued]
                ),
                ProcessingJob.started_at.is_(None),
            )
            .all()
        )
        if not stale:
            print("No stale queued/created jobs found.")
            return 0

        for job in stale:
            prior_status = job.status.value if hasattr(job.status, "value") else job.status
            proc_repo.transition(
                db, job, JobState.cancelled,
                stage=job.current_stage,
                error_code="STALE_QUEUED",
                error_message="Cancelled: enqueued but never picked up by a worker.",
            )
            project = db.get(VideoProject, job.project_id)
            if project is not None and project.status == ProjectStatus.processing_queued:
                # Let the user re-approve from the preview/result screen.
                project.status = ProjectStatus.preview_ready
            print(
                f"cancelled job {job.id} (project {job.project_id}) "
                f"was {prior_status}"
            )
        db.commit()
        print(f"Done. Cancelled {len(stale)} stale job(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
