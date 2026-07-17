"""Upload routes (SRS UPLOAD-001..007, PERF-002).

For the LocalFs backend the upload is streamed directly from the multipart body
to storage through the API process (the alternative, presigned URLs, is the
MinIO path). The initiate endpoint accepts the filename + announced size,
runs pre-flight validation, creates a project + upload row, and returns the
storage key the client will upload into. complete streams the bytes, sniffs the
container, probes metadata, and renders the proxy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.models import User, Upload, VideoProject
from app.repositories import uploads as upload_repo
from app.schemas.projects import ProjectDetail
from app.schemas.uploads import (
    UploadCompleteResponse,
    UploadInitiateRequest,
    UploadInitiateResponse,
)
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Cap an in-memory multipart read to keep the stream truly direct-to-disk.
_CHUNK = 1 << 20


@router.post("/initiate", response_model=UploadInitiateResponse, status_code=status.HTTP_201_CREATED)
def initiate_upload(
    body: UploadInitiateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadInitiateResponse:
    """Create the project + upload rows and return the upload target.

    Pre-flight validates the extension + announced size so a banned file never
    allocates storage. The project is created owned by the caller and left in
    'uploading' status until complete() finalizes it.
    """
    # The client may pass a project_id of an existing empty project (re-upload)
    # or omit it to create a new one. For MVP we always create a new project.
    if body.project_id:
        existing = upload_repo.get_project_owned(db, body.project_id, user.id)
        if existing is None:
            raise AppError("NOT_FOUND", "Project not found.", 404)
        # Re-initiate on an existing project (e.g. retry after cancel).
        upload = upload_repo.create_upload(
            db, project_id=existing.id, user_id=user.id, filename=body.filename, total_bytes=body.total_bytes
        )
        db.commit()
        db.refresh(upload)
        project = existing
    else:
        upload, project = upload_service.initiate(db, user, body.filename, body.total_bytes)

    key = upload_service.storage_key_for(project.id, body.filename)
    return UploadInitiateResponse(
        upload_id=upload.id,
        project_id=project.id,
        storage_key=key,
        bucket=upload_service.BUCKET_ORIGINAL,
        chunked=False,
        upload_url=None,
    )


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: str,
    file: UploadFile = File(...),
    declared_mime: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadCompleteResponse:
    """Stream the multipart body into storage, probe, generate proxy, finalize.

    SEC-007: storage keys + ffprobe args are built from validated values, never
    raw user input; subprocess calls use arg-lists only.
    """
    upload = upload_repo.get_upload(db, upload_id)
    if upload is None or upload.user_id != user.id:
        raise AppError("NOT_FOUND", "Upload not found.", 404)
    if upload.completed:
        raise AppError("CONFLICT", "Upload already completed.", 409)
    project = upload_repo.get_project_owned(db, upload.project_id, user.id)
    if project is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)

    if not declared_mime:
        declared_mime = file.content_type

    project = await upload_service.complete(db, upload, project, file, declared_mime)

    return UploadCompleteResponse(
        upload_id=upload.id,
        project_id=project.id,
        received_bytes=upload.received_bytes,
        completed=True,
        project=ProjectDetail.model_validate(project),
    )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_upload(
    upload_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    upload = upload_repo.get_upload(db, upload_id)
    if upload is None or upload.user_id != user.id:
        raise AppError("NOT_FOUND", "Upload not found.", 404)
    project = upload_repo.get_project_owned(db, upload.project_id, user.id)
    if project is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    upload_service.cancel(db, upload, project)
