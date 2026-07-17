"""Mask routes (SRS MASK-001..007).

PUT/GET /api/v1/projects/{id}/mask. MVP persists a single static mask
(apply_to_entire=True); the time-range variant is stubbed for Phase 5.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.models import User, VideoProject, ProjectStatus, WatermarkMask
from app.repositories import uploads as upload_repo
from app.schemas.masks import MaskRequest, MaskResponse

router = APIRouter(prefix="/projects", tags=["masks"])


def _owned_project(db: Session, project_id: str, user: User) -> VideoProject:
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if p.status in (ProjectStatus.uploading, ProjectStatus.created):
        raise AppError("CONFLICT", "Project has not finished uploading yet.", 409)
    if not p.width or not p.height:
        raise AppError("CONFLICT", "Project metadata not available yet (ffprobe).", 409)
    return p


@router.put("/{project_id}/mask", response_model=MaskResponse)
def put_mask(
    project_id: str,
    body: MaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MaskResponse:
    p = _owned_project(db, project_id, user)

    # Validate mask geometry against the project's source frame size. The
    # stored width/height is the geometry's reference frame; for MVP we coerce
    # it to the project's source dimensions.
    try:
        body.validate_geometry(int(p.width), int(p.height))
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", str(exc), 422)

    # MVP only supports the entire-video static mask (MASK-005). A custom
    # start/end that isn't None+None is recorded but Phase 5 treats it as a
    # full-range static mask.
    if not body.apply_to_entire:
        pass  # accepted; Phase 5 will honour start/end

    mask = upload_repo.save_mask(
        db,
        p,
        tool=body.tool,
        geometry=body.geometry,
        width=int(p.width),
        height=int(p.height),
        mask_expansion=body.mask_expansion,
        mask_feathering=body.mask_feathering,
        temporal_smoothing=body.temporal_smoothing,
        apply_to_entire=body.apply_to_entire,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.commit()
    db.refresh(mask)
    return MaskResponse.model_validate(mask)


@router.get("/{project_id}/mask", response_model=MaskResponse)
def get_mask(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MaskResponse:
    p = _owned_project(db, project_id, user)
    mask = upload_repo.latest_mask(db, p.id)
    if mask is None:
        raise AppError("NOT_FOUND", "No mask saved for this project.", status.HTTP_404_NOT_FOUND)
    return MaskResponse.model_validate(mask)


@router.delete("/{project_id}/mask", status_code=status.HTTP_204_NO_CONTENT)
def delete_mask(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    p = _owned_project(db, project_id, user)
    db.query(WatermarkMask).filter(WatermarkMask.project_id == p.id).delete()
    db.commit()
