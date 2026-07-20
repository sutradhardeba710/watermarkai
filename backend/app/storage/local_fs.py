"""Filesystem-backed object storage. The default dev backend (no Docker needed).

A signed URL is returned as a short-lived JWT token; the download route validates
it and streams the file. This keeps storage private (SRS STORAGE-003) without
requiring MinIO.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import IO

from jose import jwt

from app.core.config import get_settings
from app.storage.base import ObjectStorage

_settings = get_settings()


class LocalFsStorage(ObjectStorage):
    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else _settings.storage_local_path

    def _path(self, bucket: str, key: str) -> Path:
        # sanitize: no traversal outside the bucket dir
        safe_key = key.replace("\\", "/").lstrip("/")
        p = (self.root / bucket / safe_key).resolve()
        base = (self.root / bucket).resolve()
        # Path.is_relative_to (not str.startswith) so a sibling directory that
        # shares the bucket's name as a prefix (e.g. `outputs_evil`) can't pass.
        if p != base and not p.is_relative_to(base):
            raise ValueError(f"unsafe key escapes bucket: {key}")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, bucket: str, key: str, data: IO[bytes], content_type: str = "application/octet-stream") -> str:
        p = self._path(bucket, key)
        with open(p, "wb") as f:
            shutil.copyfileobj(data, f)
        return key

    def put_file(self, bucket: str, key: str, path: str, content_type: str = "application/octet-stream") -> str:
        p = self._path(bucket, key)
        # put_file preserves nesting; move via copy to be safe across volumes
        shutil.copyfile(path, p)
        return key

    def get(self, bucket: str, key: str) -> bytes:
        return self._path(bucket, key).read_bytes()

    def download_to_file(self, bucket: str, key: str, dest_path: str) -> str:
        src = self._path(bucket, key)
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest_path)
        return dest_path

    def delete(self, bucket: str, key: str) -> None:
        p = self._path(bucket, key)
        if p.exists():
            p.unlink()

    def exists(self, bucket: str, key: str) -> bool:
        return self._path(bucket, key).exists()

    def signed_download_url(self, bucket: str, key: str, expires_seconds: int) -> str:
        # We return a compact token; the /download route validates it.
        payload = {
            "bucket": bucket,
            "key": key,
            "exp": int(time.time()) + expires_seconds,
        }
        token = jwt.encode(payload, _settings.secret_key, algorithm="HS256")
        return f"token:{token}"

    @staticmethod
    def verify_signed_url(token: str) -> tuple[str, str]:
        """Decode a signed-url token; raise if invalid/expired. Returns (bucket, key)."""
        payload = jwt.decode(token, _settings.secret_key, algorithms=["HS256"])
        return payload["bucket"], payload["key"]


def parse_signed_token(url: str) -> tuple[str, str]:
    if not url.startswith("token:"):
        raise ValueError("invalid signed url scheme")
    return LocalFsStorage.verify_signed_url(url[len("token:") :])


__all__ = ["LocalFsStorage", "parse_signed_token"]
