"""Preview + download routes (SRS PREVIEW-001..006, DOWNLOAD-001..005).

  POST /api/v1/projects/{id}/preview       — build a windowed before/after
                                              preview clip at proxy resolution.
  GET  /api/v1/projects/{id}/preview       — fetch the latest preview artifact
                                              (descriptor; the bytes flow via
                                              /projects/{id}/preview-clip).
  GET  /api/v1/projects/{id}/preview-clip  — stream the preview MP4.
  POST /api/v1/projects/{id}/download-url  — signed URL for the final output.
  GET  /api/v1/projects/{id}/output        — validate + stream signed output.

Preview is run synchronously here (the window is 3/5/10s at <=720p). The full
process job (Phase 5) is asynchronous via Celery; preview is light enough to do
in-process so the result screen gets a clip back without brokering another
queue.
"""
from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import ProjectStatus, QualityMode, User, VideoProject
from app.repositories import processing as proc_repo
from app.repositories import uploads as upload_repo
from app.schemas.preview import (
    DownloadUrlRequest,
    DownloadUrlResponse,
    PreviewRequest,
    PreviewResponse,
)
from app.services import normalize
from app.services import preview as preview_svc
from app.services.compliance import gate_downloads_allowed, gate_processing_allowed, gate_unconfirmed
from app.storage.factory import get_storage

settings = get_settings()
router = APIRouter(prefix="/projects", tags=["preview"])

PREVIEW_BUCKET = "previews"
OUTPUT_BUCKET = "outputs"
PROXY_BUCKET = "proxies"


def _before_preview_key(after_key: str) -> str:
    """Return the paired source clip key for an inpainted preview artifact."""
    return after_key.replace("/preview_", "/preview_before_", 1)


def _owned_ready_project(db: Session, project_id: str, user: User) -> VideoProject:
    p = upload_repo.get_project_owned(db, project_id, user.id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if p.status in (ProjectStatus.created, ProjectStatus.uploading):
        raise AppError("CONFLICT", "Project has not finished uploading yet.", 409)
    if not p.width or not p.height:
        raise AppError("CONFLICT", "Project metadata not available yet (ffprobe).", 409)
    return p


def _require_mask(db: Session, project_id: str):
    mask = upload_repo.latest_mask(db, project_id)
    if mask is None:
        raise AppError("MASK_REQUIRED", "Save a watermark mask before previewing.", 422)
    return mask


def _resolve_window(body: PreviewRequest | None, project: VideoProject) -> tuple[float, int]:
    """Decide the preview window's start + duration. Defaults to the playhead."""
    b = body or PreviewRequest()
    duration = b.duration_seconds
    start = b.start_seconds if b.start_seconds is not None else 0.0
    # Clamp the window into the project's duration so a long playhead doesn't
    # overrun the source.
    if project.duration:
        max_start = max(0.0, project.duration - duration)
        start = min(start, max_start)
    return start, duration


@router.post("/{project_id}/preview", response_model=PreviewResponse)
def create_preview(
    project_id: str,
    body: PreviewRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreviewResponse:
    p = _owned_ready_project(db, project_id, user)
    gate_unconfirmed(upload_repo.has_confirmation(db, p.id))
    # PRD §9.5: moderation flags block preview generation too — a preview is
    # a (small) processed artifact of the source.
    gate_processing_allowed(p)
    mask = _require_mask(db, p.id)

    start, duration = _resolve_window(body, p)
    quality = (proc_repo.get_settings_row(db, p.id) or None)
    quality_mode = quality.quality_mode if quality else QualityMode.balanced

    # Mark project as preview_processing while we run.
    p.status = ProjectStatus.preview_processing
    db.commit()

    try:
        key, before_key = _build_preview_clip(p, mask, start, duration, str(quality_mode.value))
        storage = get_storage()
        # Set the project preview key + ready state.
        p.preview_storage_key = key
        p.status = ProjectStatus.preview_ready
        db.commit()
        return PreviewResponse(
            project_id=p.id,
            status="ready",
            quality_mode=quality_mode.value,
            start_seconds=start,
            duration_seconds=duration,
            artifact_storage_key=key,
            before_artifact_storage_key=before_key,
        )
    except AppError as exc:
        p.status = ProjectStatus.failed
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        p.status = ProjectStatus.failed
        db.commit()
        raise AppError("PREVIEW_FAILED", repr(exc), 502) from exc


def _build_preview_clip(
    project: VideoProject, mask, start: float, duration: int, quality: str
) -> str:
    """In-process: trim a window, inpaint its frames, encode to H.420p.

    Returns the storage key under the `previews` bucket.
    """
    import cv2  # heavy dep on the worker/server box only

    storage = get_storage()
    # Pull the source to a local temp file. We prefer the proxy for preview so
    # the inpaint runs at <=720p; fall back to the original when there's no
    # proxy yet.
    src_key = project.proxy_storage_key or project.input_storage_key
    src_bucket = PROXY_BUCKET if project.proxy_storage_key else "originals"
    if not src_key:
        raise AppError("NOT_FOUND", "Source video is not available in storage.", 404)

    work_dir = Path(tempfile.mkdtemp(prefix="vwa-preview-"))
    try:
        local_src = work_dir / "source.mp4"
        storage.download_to_file(src_bucket, src_key, str(local_src))

        # Trim window (copy codec when possible)
        trimmed = work_dir / "window.mp4"
        normalize.run_ffmpeg(preview_svc.trim_clip_args(local_src, trimmed, start, duration))

        # Re-encode to a <=720p proxy target if the source is full-res. Skip if
        # already 720p (proxy path); keeps the loop fast.
        proxy = work_dir / "proxy.mp4"
        h = project.height or 0
        if h > 720 and project.proxy_storage_key is None:
            normalize.run_ffmpeg(preview_svc.proxy_target_args(trimmed, proxy))
        else:
            proxy = trimmed

        # Extract frames
        frames_dir = work_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        normalize.run_ffmpeg(
            preview_svc.extract_window_frames_args(proxy, frames_dir, fps=project.fps)
        )
        frame_paths = sorted(frames_dir.glob("frame_*.png"))
        if not frame_paths:
            raise AppError("EXTRACT_FAILED", "Preview produced no frames.", 502)

        # Build the static mask once; resize to each frame's buffer dims.
        cache = StaticMaskForPreview(mask, int(project.width), int(project.height))
        out_dir = work_dir / "inpainted"
        out_dir.mkdir(parents=True, exist_ok=True)

        inpainter = _new_inpainter()
        prev_out = None
        for fp in frame_paths:
            frame = cv2.imread(str(fp), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            mask_u8 = cache.get_for(frame.shape[1], frame.shape[0])
            out = inpainter.inpaint_frame(frame, mask_u8, previous_frame=prev_out, quality=quality)
            cv2.imwrite(str(out_dir / fp.name), out)
            prev_out = out if quality == "high" else prev_out

        fps = float(project.fps or 25.0)
        before_clip = work_dir / "preview_before.mp4"
        normalize.run_ffmpeg(preview_svc.encode_preview_args(frames_dir, before_clip, fps=fps))

        out_clip = work_dir / "preview.mp4"
        normalize.run_ffmpeg(preview_svc.encode_preview_args(out_dir, out_clip, fps=fps))

        key = f"{project.id}/preview_{start:.1f}_{duration}.mp4"
        before_key = _before_preview_key(key)
        storage.put_file(PREVIEW_BUCKET, key, str(out_clip), content_type="video/mp4")
        storage.put_file(PREVIEW_BUCKET, before_key, str(before_clip), content_type="video/mp4")
        return key, before_key
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@router.get("/{project_id}/preview", response_model=PreviewResponse)
def get_preview(
    project_id: str,
    variant: str = Query(default="after", pattern="^(after|before)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreviewResponse:
    """Return a descriptor for the latest preview if one exists."""
    p = _owned_ready_project(db, project_id, user)
    key = _before_preview_key(p.preview_storage_key) if variant == "before" and p.preview_storage_key else p.preview_storage_key
    if not key:
        raise AppError("NOT_FOUND", "No preview artifact yet.", 404)
    return PreviewResponse(
        project_id=p.id,
        status="ready",
        quality_mode=(proc_repo.get_settings_row(db, p.id) or _default_settings(p)).quality_mode.value,
        start_seconds=0.0,
        duration_seconds=5,
        artifact_storage_key=key,
    )


class _DefaultSettings:
    quality_mode = QualityMode.balanced


def _default_settings(_p):  # pragma: no cover - pure fallback
    return _DefaultSettings()


@router.get("/{project_id}/preview-clip")
def stream_preview_clip(
    project_id: str,
    token: Optional[str] = Query(default=None),
    variant: str = Query(default="after", pattern="^(after|before)$"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Stream the latest preview MP4.

    A raw ``<video src>`` can't attach an Authorization header, so this mirrors
    the ``/proxy`` / ``/thumbnail`` routes in ``files.py``: a signed ``?token=``
    (minted by ``GET /projects/{id}``) authenticates media-element requests;
    axios callers may still use the bearer header. Either path is scoped to
    the project owner's preview artifact.
    """
    if token:
        p = _project_via_preview_token(db, project_id, token, variant)
    else:
        from app.auth.dependencies import get_authorization_scheme
        from app.core.security import verify_access_token

        scheme, tok = get_authorization_scheme(authorization)
        if not tok:
            raise AppError("UNAUTHORIZED", "Missing or invalid authorization header.", 401)
        try:
            payload = verify_access_token(tok)
        except Exception as exc:  # noqa: BLE001
            raise AppError("UNAUTHORIZED", "Invalid or expired token.", 401) from exc
        user = db.get(User, payload["sub"])
        if user is None:
            raise AppError("UNAUTHORIZED", "User not found.", 401)
        p = _owned_ready_project(db, project_id, user)

    key = _before_preview_key(p.preview_storage_key) if variant == "before" and p.preview_storage_key else p.preview_storage_key
    if not key:
        raise AppError("NOT_FOUND", "No preview artifact yet.", 404)

    storage = get_storage()
    from app.storage.local_fs import LocalFsStorage

    if isinstance(storage, LocalFsStorage):
        path = (settings.storage_local_path / PREVIEW_BUCKET / key).resolve()
        if not path.exists():
            raise AppError("NOT_FOUND", "Preview file missing from storage.", 404)
        return FileResponse(str(path), media_type="video/mp4")
    data = storage.get(PREVIEW_BUCKET, key)
    return JSONResponse(content={"error": "backend_not_local"},
                        status_code=502)  # MinIO path: bytes via Response in a later polish


def _project_via_preview_token(db: Session, project_id: str, token: str, variant: str = "after") -> VideoProject:
    """Resolve the project from a signed preview media token (raw <video> path).

    Mirrors ``files._project_via_token`` but for the ``previews`` bucket +
    ``preview_storage_key`` field. Raises if the token doesn't match this
    project's preview artifact.
    """
    from app.storage.local_fs import parse_signed_token

    try:
        bucket, key = parse_signed_token(f"token:{token}")
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_TOKEN", "Invalid or expired media token.", 403) from exc

    p = db.get(VideoProject, project_id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    expected_key = _before_preview_key(p.preview_storage_key) if variant == "before" and p.preview_storage_key else p.preview_storage_key
    if bucket != PREVIEW_BUCKET or not expected_key or key != expected_key:
        raise AppError("FORBIDDEN", "Token does not match this artifact.", 403)
    if p.status in (ProjectStatus.created, ProjectStatus.uploading):
        raise AppError("CONFLICT", "Project has not finished uploading yet.", 409)
    return p


# --- Signed download URL (DOWNLOAD-001..005) ---


@router.post("/{project_id}/download-url", response_model=DownloadUrlResponse)
def issue_download_url(
    project_id: str,
    body: DownloadUrlRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DownloadUrlResponse:
    """Return a signed URL for the project's finalized output. Requires the
    project to be in `completed` state (Phase 5 sets it). DOWNLOAD-003 expiry
    is configurable up to 24h."""
    p = _owned_ready_project(db, project_id, user)
    if p.status != ProjectStatus.completed or not p.output_storage_key:
        raise AppError("CONFLICT", "Output is not available — process the project first.", 409)
    # PRD §9.5: locked / downloads-disabled projects must not mint signed URLs.
    gate_downloads_allowed(p)

    b = body or DownloadUrlRequest()
    storage = get_storage()
    url = storage.signed_download_url(OUTPUT_BUCKET, p.output_storage_key, b.expires_seconds)
    from datetime import datetime, timedelta, timezone

    exp = datetime.now(timezone.utc) + timedelta(seconds=b.expires_seconds)
    return DownloadUrlResponse(
        bucket=OUTPUT_BUCKET,
        key=p.output_storage_key,
        url=url,
        expires_seconds=b.expires_seconds,
        expires_at=exp,
    )


@router.get("/{project_id}/output")
def stream_signed_output(
    project_id: str,
    token: Optional[str] = Query(default=None),
    variant: str = Query(default="after", pattern="^(after|before)$"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Validate the signed token from POST /download-url and stream the MP4.

    Download is triggered via ``window.open(.../output?token=...)`` from the
    result screen, which (like a raw ``<video src>``) cannot attach an
    Authorization header. So the signed ``?token=`` authenticates the request
    and is scoped to this project's ``output_storage_key`` — it is only minted
    by ``POST /download-url``, which itself requires the project owner's
    bearer. Axios callers may still use the bearer header as a fallback.
    """
    from app.storage.local_fs import parse_signed_token
    from fastapi import Response

    if token:
        p = _project_via_output_token(db, project_id, token)
    else:
        from app.auth.dependencies import get_authorization_scheme
        from app.core.security import verify_access_token

        scheme, tok = get_authorization_scheme(authorization)
        if not tok:
            raise AppError("UNAUTHORIZED", "Missing or invalid authorization header.", 401)
        try:
            payload = verify_access_token(tok)
        except Exception as exc:  # noqa: BLE001
            raise AppError("UNAUTHORIZED", "Invalid or expired token.", 401) from exc
        user = db.get(User, payload["sub"])
        if user is None:
            raise AppError("UNAUTHORIZED", "User not found.", 401)
        p = _owned_ready_project(db, project_id, user)

    key = p.output_storage_key
    if not key:
        raise AppError("NOT_FOUND", "Output is not available — process the project first.", 404)
    if p.status != ProjectStatus.completed:
        raise AppError("CONFLICT", "Output is not available — process the project first.", 409)
    # PRD §9.5: enforce at stream time as well — a token minted before the
    # moderation flag was set must stop working immediately.
    gate_downloads_allowed(p)

    storage = get_storage()
    from app.storage.local_fs import LocalFsStorage

    if isinstance(storage, LocalFsStorage):
        path = (settings.storage_local_path / OUTPUT_BUCKET / key).resolve()
        if not path.exists():
            raise AppError("NOT_FOUND", "Output file missing from storage.", 404)
        return FileResponse(str(path), media_type="video/mp4")
    data = storage.get(OUTPUT_BUCKET, key)
    return Response(content=data, media_type="video/mp4")


def _project_via_output_token(db: Session, project_id: str, token: str) -> VideoProject:
    """Resolve the project from a signed download token (window.open path).

    Mirrors ``_project_via_preview_token`` but for the ``outputs`` bucket +
    ``output_storage_key`` field. The token is minted by ``issue_download_url``
    (owner-scoped via ``get_current_user``), so a matching token here proves the
    caller is entitled to this project's finalized output.
    """
    from app.storage.local_fs import parse_signed_token

    try:
        bucket, key = parse_signed_token(f"token:{token}")
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_TOKEN", "Invalid or expired download URL.", 403) from exc

    p = db.get(VideoProject, project_id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    if bucket != OUTPUT_BUCKET or not p.output_storage_key or key != p.output_storage_key:
        raise AppError("FORBIDDEN", "Token does not belong to this project.", 403)
    return p


# --- Helpers ---


def _new_inpainter():
    import workers.ai_models_paths  # noqa: F401 — alias ai_models
    from ai_models.inpainting.opencv_inpainter import OpenCVInpainter

    return OpenCVInpainter()


class StaticMaskForPreview:
    """Builds an inpaint mask resized to each emitted frame's buffer dims.

    Mirrors workers' StaticMaskCache but is happy to be called from the API
    process (numpy imported lazily inside the cache get).
    """
    def __init__(self, mask, frame_w: int, frame_h: int):
        self._mask = mask
        self._frame_w = frame_w
        self._frame_h = frame_h
        self._base = None

    def get_for(self, w: int, h: int) -> object:
        import cv2

        if self._base is None:
            from app.services.mask_render import resolve_inpaint_mask

            self._base = resolve_inpaint_mask(
                self._mask.tool,
                self._mask.geometry,
                self._frame_w,
                self._frame_h,
                mask_expansion=self._mask.mask_expansion,
                mask_feathering=self._mask.mask_feathering,
            )
        if self._base.shape[:2] != (h, w):
            return cv2.resize(self._base, (w, h), interpolation=cv2.INTER_NEAREST)
        return self._base


__all__ = ["router"]
