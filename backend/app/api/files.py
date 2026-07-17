"""File-streaming routes (proxy / thumbnail / preview / output).

Streams object-storage content back to the browser. The proxy + thumbnail
artifacts are served to raw ``<video src>`` / ``<img src>`` elements, which
cannot attach an Authorization header. Those requests authenticate via a
short-lived signed ``?token=`` minted by ``GET /projects/{id}``. Axios callers
may still use the bearer header. Either path is scoped to the project owner's
artifacts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_authorization_scheme
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import verify_access_token
from app.models import User, VideoProject, ProjectStatus
from app.repositories import uploads as upload_repo
from app.storage.factory import get_storage

router = APIRouter(prefix="/projects", tags=["files"])

ALLOWED_KINDS = {"proxy": "proxy_storage_key", "thumbnail": "thumbnail_storage_key"}
_KIND_TO_BUCKET = {"proxy": "proxies", "thumbnail": "thumbnails"}

# Signed media tokens live 1h: long enough for an editing session, short enough
# that a leaked <video src> URL is low-value and scoped to one artifact.
_MEDIA_TOKEN_TTL = 3600


def _project_via_token(db: Session, project_id: str, kind: str, token: str) -> VideoProject:
    """Resolve the project from a signed media token (raw <video>/<img> path)."""
    from app.storage.local_fs import parse_signed_token

    try:
        bucket, key = parse_signed_token(f"token:{token}")
    except Exception as exc:  # noqa: BLE001
        raise AppError("BAD_TOKEN", "Invalid or expired media token.", 403) from exc

    p = db.get(VideoProject, project_id)
    if p is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    expected_bucket = _KIND_TO_BUCKET[kind]
    expected_key = getattr(p, ALLOWED_KINDS[kind], None)
    if bucket != expected_bucket or not expected_key or key != expected_key:
        raise AppError("FORBIDDEN", "Token does not match this artifact.", 403)
    return p


def _user_via_bearer(authorization: Optional[str], db: Session) -> User:
    """Resolve the caller from a bearer header (axios path)."""
    scheme, token = get_authorization_scheme(authorization)
    if not token:
        raise AppError("UNAUTHORIZED", "Missing token or authorization header.", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = verify_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AppError("UNAUTHORIZED", "Invalid or expired token.", status.HTTP_401_UNAUTHORIZED) from exc
    user = db.get(User, payload["sub"])
    if user is None:
        raise AppError("UNAUTHORIZED", "User not found.", status.HTTP_401_UNAUTHORIZED)
    return user


@router.get("/{project_id}/{kind}")
def stream_artifact(
    project_id: str,
    kind: str,
    token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if kind not in ALLOWED_KINDS:
        raise AppError("NOT_FOUND", "Unknown artifact kind.", 404)

    if token:
        p = _project_via_token(db, project_id, kind, token)
    else:
        user = _user_via_bearer(authorization, db)
        p = upload_repo.get_project_owned(db, project_id, user.id)
        if p is None:
            raise AppError("NOT_FOUND", "Project not found.", 404)

    key = getattr(p, ALLOWED_KINDS[kind])
    if not key:
        raise AppError("NOT_FOUND", "Artifact not available.", 404)
    if kind == "proxy" and p.status in (ProjectStatus.created, ProjectStatus.uploading):
        raise AppError("CONFLICT", "Upload not finalized yet.", 409)

    storage = get_storage()
    settings = get_settings()
    bucket = _KIND_TO_BUCKET[kind]
    media = "video/mp4" if kind == "proxy" else "image/jpeg"

    # Fast path for LocalFs: serve the file directly from disk, no copy.
    from app.storage.local_fs import LocalFsStorage

    if isinstance(storage, LocalFsStorage):
        path = (settings.storage_local_path / bucket / key).resolve()
        if not path.exists():
            raise AppError("NOT_FOUND", "Artifact file missing from storage.", 404)
        return FileResponse(str(path), media_type=media)

    # Other backends: pull bytes through the storage interface.
    try:
        data = storage.get(bucket, key)
    except Exception as exc:  # noqa: BLE001
        raise AppError("STORAGE_ERROR", "Could not read artifact.", 502) from exc
    from fastapi import Response

    return Response(content=data, media_type=media)


__all__ = ["router", "_MEDIA_TOKEN_TTL"]
