"""Projects routes.

Phase 2 shipped read-only GET list/detail. Phase 3 adds POST creation + the
legal/compliance confirmation endpoint, scoped to the project owner.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.models import (
    ComplianceConfirmation,
    JobState,
    ProcessingJob,
    ProcessingSetting,
    ProjectStatus,
    User,
    VideoProject,
    WatermarkMask,
)
from app.repositories import processing as processing_repo
from app.repositories import uploads as upload_repo
from app.schemas.projects import ProjectSummary, ProjectDetail
from app.schemas.uploads import (
    ComplianceConfirmRequest,
    ComplianceConfirmResponse,
    ProjectCreateRequest,
)
from app.services import compliance

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProjectSummary]:
    """DASH-001..004: list user's projects with optional filter/search."""
    qry = db.query(VideoProject).filter(VideoProject.user_id == user.id, VideoProject.deleted == False)  # noqa: E712
    if status_filter:
        try:
            status_enum = ProjectStatus(status_filter)
        except ValueError:
            raise AppError("VALIDATION_ERROR", f"Unknown status filter '{status_filter}'.", 422)
        qry = qry.filter(VideoProject.status == status_enum)
    if q:
        like = f"%{q}%"
        qry = qry.filter((VideoProject.title.ilike(like)) | (VideoProject.original_filename.ilike(like)))
    rows = qry.order_by(VideoProject.created_at.desc()).limit(100).all()
    summaries: list[ProjectSummary] = []
    for row in rows:
        summary = ProjectSummary.model_validate(row)
        _attach_signed_media_urls(summary, row)
        summaries.append(summary)
    return summaries


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectDetail:
    p = db.get(VideoProject, project_id)
    if p is None or p.user_id != user.id:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    detail = ProjectDetail.model_validate(p)
    _attach_signed_media_urls(detail, p)
    return detail


def _attach_signed_media_urls(detail: ProjectSummary, p: VideoProject) -> None:
    """Mint short-lived signed URLs so a raw <video src>/<img src> can fetch the
    proxy/thumbnail without an Authorization header (browsers can't attach one
    to media-element requests). Reuses the Phase 6 signed-token machinery."""
    from app.api.files import _MEDIA_TOKEN_TTL
    from app.storage.factory import get_storage

    storage = get_storage()
    # These routes stream bytes via storage.get() and authenticate with the
    # app's own JWT (?token=). Mint that JWT directly — storage.signed_download_url
    # returns an S3 presigned URL on the minio backend, which the app routes
    # can't parse (403 / black media element).
    from app.storage.local_fs import mint_signed_token

    if p.proxy_storage_key:
        detail.proxy_url = f"/api/v1/projects/{p.id}/proxy?token={mint_signed_token('proxies', p.proxy_storage_key, _MEDIA_TOKEN_TTL)}"
    if p.thumbnail_storage_key:
        detail.thumbnail_url = f"/api/v1/projects/{p.id}/thumbnail?token={mint_signed_token('thumbnails', p.thumbnail_storage_key, _MEDIA_TOKEN_TTL)}"
    if p.preview_storage_key and isinstance(detail, ProjectDetail):
        detail.preview_url = f"/api/v1/projects/{p.id}/preview-clip?token={mint_signed_token('previews', p.preview_storage_key, _MEDIA_TOKEN_TTL)}"
        from app.api.preview import _before_preview_key
        before_key = _before_preview_key(p.preview_storage_key)
        if storage.exists("previews", before_key):
            detail.before_preview_url = f"/api/v1/projects/{p.id}/preview-clip?variant=before&token={mint_signed_token('previews', before_key, _MEDIA_TOKEN_TTL)}"


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectDetail:
    """Create a project row that an upload will be attached to.

    Validates the filename allowlist up front so we never allocate a row for a
    banned file. The project starts in 'uploading' status.
    """
    from app.services import validation

    v = validation.validate_extension(body.filename)
    if not v.ok:
        raise AppError(v.code, v.message, 400, v.details)
    if body.total_bytes is not None:
        v = validation.validate_size(body.total_bytes)
        if not v.ok:
            raise AppError(v.code, v.message, 400, v.details)
    safe = validation.sanitize_filename(body.filename)
    project = upload_repo.create_project(
        db,
        user_id=user.id,
        title=body.title or safe,
        original_filename=safe,
        total_bytes=body.total_bytes,
    )
    db.commit()
    db.refresh(project)
    return ProjectDetail.model_validate(project)


@router.post("/{project_id}/duplicate", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def duplicate_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectDetail:
    """Create an editable copy using the same owned source and copied settings."""
    source = upload_repo.get_project_owned(db, project_id, user.id)
    if source is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if not source.input_storage_key:
        raise AppError("CONFLICT", "Upload the source video before duplicating this project.", 409)

    duplicate = VideoProject(
        user_id=user.id,
        title=f"{source.title} (copy)"[:255],
        original_filename=source.original_filename,
        input_storage_key=source.input_storage_key,
        proxy_storage_key=source.proxy_storage_key,
        thumbnail_storage_key=source.thumbnail_storage_key,
        status=ProjectStatus.uploaded,
        duration=source.duration,
        width=source.width,
        height=source.height,
        fps=source.fps,
        frame_count=source.frame_count,
        video_codec=source.video_codec,
        audio_codec=source.audio_codec,
        has_audio=source.has_audio,
        file_size=source.file_size,
    )
    db.add(duplicate)
    db.flush()

    source_mask = upload_repo.latest_mask(db, source.id)
    if source_mask is not None:
        db.add(WatermarkMask(
            project_id=duplicate.id,
            tool=source_mask.tool,
            geometry=source_mask.geometry,
            width=source_mask.width,
            height=source_mask.height,
            mask_expansion=source_mask.mask_expansion,
            mask_feathering=source_mask.mask_feathering,
            temporal_smoothing=source_mask.temporal_smoothing,
            apply_to_entire=source_mask.apply_to_entire,
            start_time=source_mask.start_time,
            end_time=source_mask.end_time,
        ))

    source_settings = processing_repo.get_settings_row(db, source.id)
    if source_settings is not None:
        db.add(ProcessingSetting(
            project_id=duplicate.id,
            quality_mode=source_settings.quality_mode,
            mask_expansion=source_settings.mask_expansion,
            mask_feathering=source_settings.mask_feathering,
            temporal_smoothing=source_settings.temporal_smoothing,
            output_resolution=source_settings.output_resolution,
            output_codec=source_settings.output_codec,
            preserve_audio=source_settings.preserve_audio,
        ))

    source_confirmation = (
        db.query(ComplianceConfirmation)
        .filter(ComplianceConfirmation.project_id == source.id)
        .order_by(ComplianceConfirmation.confirmed_at.desc())
        .first()
    )
    if source_confirmation is not None:
        upload_repo.record_confirmation(
            db,
            user_id=user.id,
            project_id=duplicate.id,
            policy_version=source_confirmation.confirmation_version,
            ip_hash=source_confirmation.ip_hash,
            user_agent=source_confirmation.user_agent,
        )

    db.commit()
    db.refresh(duplicate)
    detail = ProjectDetail.model_validate(duplicate)
    _attach_signed_media_urls(detail, duplicate)
    return detail


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Soft-delete a project and stop any non-terminal jobs attached to it."""
    project = upload_repo.get_project_owned(db, project_id, user.id)
    if project is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)

    terminal = (JobState.completed, JobState.failed, JobState.cancelled, JobState.expired)
    active_jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.project_id == project.id, ProcessingJob.status.notin_(terminal))
        .all()
    )
    for job in active_jobs:
        job.status = JobState.cancelled
        job.current_stage = "cancelled"
        job.error_code = "PROJECT_DELETED"
        job.error_message = "Project deleted by its owner."
    project.deleted = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "0.0.0.0"


@router.post("/{project_id}/compliance", response_model=ComplianceConfirmResponse)
def confirm_compliance(
    project_id: str,
    body: ComplianceConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ComplianceConfirmResponse:
    """Record the LEGAL-001/002 ownership confirmation for this project.

    Subsequent POST /analyze and POST /process on this project gate on the
    presence of this row (LEGAL-003).
    """
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if not body.ownership_confirmed:
        raise AppError("LEGAL_CONFIRMATION_REQUIRED", "Ownership must be confirmed.", 403)
    rec = upload_repo.record_confirmation(
        db,
        user_id=user.id,
        project_id=project_id,
        policy_version=body.policy_version,
        ip_hash=compliance.hash_ip(_client_ip(request)),
        user_agent=compliance.summarize_ua(request.headers.get("user-agent")),
    )
    db.commit()
    db.refresh(rec)
    return ComplianceConfirmResponse.model_validate(rec)
