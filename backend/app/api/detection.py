"""Phase 7 detection routes (SRS DETECT-001..007, AI-001/002/004/006/007/008).

  POST /api/v1/projects/{id}/analyze       — enqueue an analyze job.
  GET  /api/v1/projects/{id}/candidates    — list candidates for a project.
  GET  /api/v1/candidates/{id}             — single candidate detail.
  POST /api/v1/candidates/{id}/approve     — promote to WatermarkMask.

Authorization follows the same pattern as the Phase 5 processing route: only
the project owner can analyze / read / approve. Legal gating (LEGAL-003) is
applied to the analyze trigger; the read endpoints are read-only and don't
need extra gates.

Progress is delivered by the Phase 5 SSE stream (:func:`stream_job_events`)
reused for the analyze job id — same ``job_events:{id}`` namespace.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.models import JobState, JobType, ProjectStatus, QualityMode, User, VideoProject
from app.repositories import candidates as cand_repo
from app.repositories import processing as proc_repo
from app.repositories import uploads as upload_repo
from app.schemas.candidates import (
    AnalyzeResponse,
    ApproveCandidateRequest,
    ApproveCandidateResponse,
    CandidateListResponse,
    CandidateResponse,
)
from app.services.compliance import gate_unconfirmed

project_router = APIRouter(prefix="/projects", tags=["detection"])
candidate_router = APIRouter(prefix="/candidates", tags=["detection"])


def _owned_project(db: Session, project_id: str, user: User) -> VideoProject:
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    return p


def _active_analyze(db: Session, project_id: str):
    """Existing analyze jobs that are still running. Used to keep the
    enqueue idempotent."""
    jobs = proc_repo.list_jobs_for_project(db, project_id)
    for j in jobs:
        if j.job_type == JobType.analyze and j.status in (
            JobState.created, JobState.processing_queued, JobState.analyzing,
        ):
            return j
    return None


@project_router.post(
    "/{project_id}/analyze",
    response_model=AnalyzeResponse,
    status_code=202,
)
def enqueue_analyze(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    rerun: bool = False,
) -> AnalyzeResponse:
    """Enqueue an analyze job (DETECT-007). Legal + uploading state guards."""
    p = _owned_project(db, project_id, user)
    if p.deleted:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if p.status in (ProjectStatus.uploading, ProjectStatus.created):
        raise AppError("CONFLICT",
                       "Project has not finished uploading yet.", 409)
    # LEGAL-003: gate analyze + process behind ownership confirmation.
    gate_unconfirmed(upload_repo.has_confirmation(db, p.id))

    existing = _active_analyze(db, p.id)
    if existing is not None:
        return AnalyzeResponse(job_id=existing.id, project_id=p.id,
                               status=existing.status.value)

    if rerun:
        # wipe prior runs so the next analysis starts fresh
        cand_repo.clear_candidates_for(db, p.id)
        db.commit()

    # Detect fights need a job row in the same ProcessingJob table the SSE
    # stream already knows about (DETECT-007 reuses Phase 5's machinery).
    job = proc_repo.create_job(db, p, job_type=JobType.analyze,
                               quality_mode=QualityMode.balanced)
    proc_repo.transition(db, job, JobState.processing_queued, stage="queued")
    p.status = ProjectStatus.analyzing
    db.commit()
    db.refresh(job)

    # Imported lazily so a missing Celery import doesn't crash the route layer
    # in tests that bypass the broker. Import workers.celery_app first so the
    # @shared_task binds to our app (broker_url/queues); see app/api/processing.py.
    import workers.celery_app  # noqa: F401
    from workers.tasks.detection import analyze_video

    analyze_video.apply_async(args=(job.id, p.id), queue="detection")
    return AnalyzeResponse(job_id=job.id, project_id=p.id,
                           status=job.status.value)


@project_router.get(
    "/{project_id}/candidates",
    response_model=CandidateListResponse,
)
def list_candidates(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    approved_only: bool = False,
) -> CandidateListResponse:
    """Return ranked candidates (DETECT-005). Empty list + needs_manual when
    nothing met the threshold (DETECT-006)."""
    p = _owned_project(db, project_id, user)
    rows = cand_repo.list_candidates(db, p.id, approved_only=approved_only)
    needs_manual = len(rows) == 0
    notes = None
    if needs_manual:
        notes = ("No candidate met the detection threshold. "
                 "Use the manual mask editor to draw the watermark region.")
    return CandidateListResponse(
        project_id=p.id,
        candidates=[CandidateResponse.model_validate(r) for r in rows],
        needs_manual_selection=needs_manual,
        notes=notes,
    )


@candidate_router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
)
def get_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CandidateResponse:
    row = cand_repo.get_candidate_owned(db, candidate_id, user.id)
    if row is None:
        raise AppError("NOT_FOUND", "Candidate not found.", 404)
    return CandidateResponse.model_validate(row)


@candidate_router.post(
    "/{candidate_id}/approve",
    response_model=ApproveCandidateResponse,
)
def approve_candidate(
    candidate_id: str,
    body: ApproveCandidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApproveCandidateResponse:
    """Promote a candidate into a WatermarkMask (DETECT-007)."""
    row = cand_repo.get_candidate_owned(db, candidate_id, user.id)
    if row is None:
        raise AppError("NOT_FOUND", "Candidate not found.", 404)
    project = db.get(VideoProject, row.project_id)
    if project is None or not project.width or not project.height:
        raise AppError("CONFLICT",
                       "Project metadata not available yet.", 409)

    mask = cand_repo.candidate_to_mask(
        db, row.project_id, user.id, row,
        width=int(project.width), height=int(project.height),
        mask_expansion=body.mask_expansion,
        mask_feathering=body.mask_feathering,
        temporal_smoothing=body.temporal_smoothing,
    )
    # Mark the project as ready for a follow-up processing step.
    project.status = ProjectStatus.uploaded
    db.commit()
    db.refresh(mask)

    return ApproveCandidateResponse(
        candidate_id=row.id,
        project_id=row.project_id,
        mask_id=mask.id,
        message="Candidate promoted to mask.",
    )


__all__ = ["project_router", "candidate_router"]
