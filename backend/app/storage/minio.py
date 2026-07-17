"""MinIO / S3-compatible object storage backend."""
from __future__ import annotations

from typing import IO

from app.core.config import get_settings
from app.storage.base import ObjectStorage

_settings = get_settings()


class MinioStorage(ObjectStorage):
    def __init__(self) -> None:
        from minio import Minio

        self._client = Minio(
            _settings.minio_endpoint,
            access_key=_settings.minio_access_key,
            secret_key=_settings.minio_secret_key,
            secure=_settings.minio_secure,
        )
        self._prefix = _settings.minio_bucket_prefix.rstrip("-")

    def _bucket(self, bucket: str) -> str:
        name = f"{self._prefix}-{bucket}"
        if not self._client.bucket_exists(name):
            self._client.make_bucket(name)
        return name

    def put(self, bucket: str, key: str, data: IO[bytes], content_type: str = "application/octet-stream") -> str:
        from io import BytesIO

        raw = data.read()
        self._client.put_object(self._bucket(bucket), key, BytesIO(raw), length=len(raw), content_type=content_type)
        return key

    def put_file(self, bucket: str, key: str, path: str, content_type: str = "application/octet-stream") -> str:
        self._client.fput_object(self._bucket(bucket), key, path, content_type=content_type)
        return key

    def get(self, bucket: str, key: str) -> bytes:
        obj = self._client.get_object(self._bucket(bucket), key)
        try:
            return obj.read()
        finally:
            obj.close()
            obj.release_conn()

    def download_to_file(self, bucket: str, key: str, dest_path: str) -> str:
        self._client.fget_object(self._bucket(bucket), key, dest_path)
        return dest_path

    def delete(self, bucket: str, key: str) -> None:
        self._client.remove_object(self._bucket(bucket), key)

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket(bucket), key)
            return True
        except Exception:
            return False

    def signed_download_url(self, bucket: str, key: str, expires_seconds: int) -> str:
        from datetime import timedelta

        return self._client.presigned_get_object(
            self._bucket(bucket), key, expires=timedelta(seconds=expires_seconds)
        )
