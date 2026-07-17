"""Storage backend factory selected by VWA_STORAGE_BACKEND."""
from __future__ import annotations

from app.core.config import get_settings
from app.storage.base import ObjectStorage

_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.storage_backend == "minio":
            from app.storage.minio import MinioStorage

            _storage = MinioStorage()
        else:
            from app.storage.local_fs import LocalFsStorage

            _storage = LocalFsStorage()
    return _storage
