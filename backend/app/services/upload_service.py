"""Upload orchestration service (SRS UPLOAD-001..007, PERF-002).

For the default LocalFs backend the upload is streamed directly to a temp file
under storage then atomically moved to its final key. For MinIO the initiate
route returns a presigned upload URL and the bytes never touch the API process.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import ProjectStatus, Upload, VideoProject, User
from app.repositories import uploads as upload_repo
from app.services import normalize, validation
from app.storage.factory import get_storage

# Logical buckets (SRS STORAGE-002).
BUCKET_ORIGINAL = "originals"
BUCKET_PROXY = "proxies"
BUCKET_THUMB = "thumbnails"
BUCKET_AUDIO = "audio"

# How many bytes of the head to read for MIME sniffing.
_SNIFF_BYTES = 16


def storage_key_for(project_id: str, filename: str) -> str:
    """Build a collision-safe storage key under the project scope."""
    safe = validation.sanitize_filename(filename)
    return f"{project_id}/{safe}"


def initiate(db: Session, user: User, filename: str, total_bytes: int | None) -> tuple[Upload, VideoProject]:
    """Pre-flight checks applied to the client-supplied filename + announced size
    before we ever allocate storage. Returns the freshly created Upload (and the
    project it belongs to)."""
    v = validation.validate_extension(filename)
    if not v.ok:
        raise AppError(v.code, v.message, 400, v.details)
    v = validation.validate_size(total_bytes)
    if not v.ok:
        raise AppError(v.code, v.message, 400, v.details)

    project = upload_repo.create_project(db, user_id=user.id, title=filename, original_filename=filename, total_bytes=total_bytes)
    upload = upload_repo.create_upload(db, project_id=project.id, user_id=user.id, filename=filename, total_bytes=total_bytes)
    db.commit()
    db.refresh(project)
    db.refresh(upload)
    return upload, project


async def complete(
    db: Session,
    upload: Upload,
    project: VideoProject,
    file_obj: UploadFile | Any,
    declared_mime: str | None,
) -> VideoProject:
    """Stream the upload to disk, validate content, probe, proxy, finalize.

    The byte stream is consumed on the event loop (async reads); everything
    after — MIME sniff, ffprobe, proxy/thumbnail transcodes, storage copies —
    is CPU/subprocess-bound and runs in a worker thread so a 10-minute ffmpeg
    transcode doesn't freeze every other request on the server.
    """
    settings = get_settings()

    safe = validation.sanitize_filename(upload.filename)
    final_key = storage_key_for(project.id, safe)

    # Stream into a temp file first so a failed validation never leaves a
    # half-written object in originals/.
    tmp_path = Path(tempfile.mkdtemp(prefix="vwa-up-")) / safe
    received = 0
    head = bytearray()
    declared_max = settings.max_file_size_mb * 1024 * 1024
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file_obj.read(1 << 20)
                if not chunk:
                    break
                received += len(chunk)
                if received > declared_max:
                    raise AppError("FILE_TOO_LARGE", "Upload exceeded the size limit mid-stream.")
                if len(head) < _SNIFF_BYTES:
                    head.extend(chunk[: _SNIFF_BYTES - len(head)])
                out.write(chunk)
        upload_repo.set_upload_progress(db, upload, received)
    except AppError:
        shutil.rmtree(tmp_path.parent, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(tmp_path.parent, ignore_errors=True)
        raise AppError("UPLOAD_ERROR", "Failed to write upload to disk.", 502) from exc

    return await asyncio.to_thread(
        _finalize_upload, db, upload, project, tmp_path, final_key,
        bytes(head), declared_mime, received,
    )


def _finalize_upload(
    db: Session,
    upload: Upload,
    project: VideoProject,
    tmp_path: Path,
    final_key: str,
    head: bytes,
    declared_mime: str | None,
    received: int,
) -> VideoProject:
    """Blocking half of :func:`complete` — runs in a thread off the event loop."""
    # Content sniff on the saved head (SEC-004).
    v = validation.validate_mime(head, declared_mime)
    if not v.ok:
        shutil.rmtree(tmp_path.parent, ignore_errors=True)
        raise AppError(v.code, v.message, 415, v.details)

    # Persist the original + extract metadata.
    storage = get_storage()
    storage.put_file(BUCKET_ORIGINAL, final_key, str(tmp_path), content_type=declared_mime or "application/octet-stream")

    try:
        meta = validation.probe_container(tmp_path)
    except AppError:
        storage.delete(BUCKET_ORIGINAL, final_key)
        shutil.rmtree(tmp_path.parent, ignore_errors=True)
        raise

    v = validation.enforce_limits(meta)
    if not v.ok:
        storage.delete(BUCKET_ORIGINAL, final_key)
        shutil.rmtree(tmp_path.parent, ignore_errors=True)
        raise AppError(v.code, v.message, 413, v.details)

    upload_repo.attach_metadata(db, project, meta)
    project.file_size = received
    project.input_storage_key = final_key

    # Proxy + (optional) audio separation. These are best-effort at the MVP
    # layer: if ffmpeg is missing we still mark the upload uploaded so the
    # manual-mask path (Phase 4, which only needs the proxy) can degrade
    # gracefully and surface the gap. We track whether the proxy succeeded so
    # the API can warn the frontend the canvas may be unavailable.
    proxy_ok = False
    try:
        proxy_key = f"{project.id}/proxy.mp4"
        proxy_dst = Path(tempfile.mkdtemp(prefix="vwa-proxy-")) / "proxy.mp4"
        normalize.run_ffmpeg(normalize.proxy_args(tmp_path, proxy_dst))
        storage.put_file(BUCKET_PROXY, proxy_key, str(proxy_dst), content_type="video/mp4")
        project.proxy_storage_key = proxy_key
        proxy_ok = True
        shutil.rmtree(proxy_dst.parent, ignore_errors=True)

        if meta.get("has_audio"):
            audio_key = f"{project.id}/audio_orig"
            audio_dst = Path(tempfile.mkdtemp(prefix="vwa-aud-")) / "audio.bin"
            normalize.run_ffmpeg(normalize.split_audio_args(tmp_path, audio_dst))
            storage.put_file(BUCKET_AUDIO, audio_key, str(audio_dst), content_type="audio/aac")
            shutil.rmtree(audio_dst.parent, ignore_errors=True)
    except AppError:
        # Proxy missing degrades Phase 4 (mask canvas) but does not block the
        # upload itself; project proceeds in 'uploaded' so the user can retry.
        pass

    thumb_key = None
    try:
        thumb_key = f"{project.id}/thumb.jpg"
        thumb_dst = Path(tempfile.mkdtemp(prefix="vwa-thumb-")) / "thumb.jpg"
        normalize.run_ffmpeg(normalize.thumbnail_args(tmp_path, thumb_dst))
        storage.put_file(BUCKET_THUMB, thumb_key, str(thumb_dst), content_type="image/jpeg")
        project.thumbnail_storage_key = thumb_key
        shutil.rmtree(thumb_dst.parent, ignore_errors=True)
    except AppError:
        pass

    upload_repo.finalize_upload(db, upload, storage_key=final_key, received_bytes=received)
    upload_repo.mark_completed(db, project, ProjectStatus.uploaded)
    db.commit()
    db.refresh(project)

    # The temp upload file is now safely copied into storage; clean up.
    shutil.rmtree(tmp_path.parent, ignore_errors=True)

    # Attach a transient flag so the route layer can warn about a failed proxy
    # without persisting it. The "uploaded" status stays valid either way.
    setattr(project, "_proxy_ok", proxy_ok)
    return project


def cancel(db: Session, upload: Upload, project: VideoProject) -> None:
    """Cancel an in-flight upload (UPLOAD-007): mark rows + drop any stored bytes."""
    storage = get_storage()
    if project.input_storage_key:
        storage.delete(BUCKET_ORIGINAL, project.input_storage_key)
    upload_repo.cancel_upload(db, upload)
    upload_repo.mark_status(db, project, ProjectStatus.cancelled)
    db.commit()


__all__ = [
    "initiate",
    "complete",
    "cancel",
    "storage_key_for",
    "BUCKET_ORIGINAL",
    "BUCKET_PROXY",
    "BUCKET_THUMB",
    "BUCKET_AUDIO",
]
