"""Object storage abstraction.

Two implementations honor the same interface so the dev machine can run
without Docker (LocalFsStorage, the default) and production can use
MinioStorage. SRS STORAGE-001..006.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import IO


class ObjectStorage(ABC):
    """Minimal object-storage interface used across the app.

    Logical buckets (SRS STORAGE-002): original, proxy, frames, masks,
    previews, outputs, thumbnails.
    """

    @abstractmethod
    def put(self, bucket: str, key: str, data: IO[bytes], content_type: str = "application/octet-stream") -> str:
        """Store bytes; return a storage key/path identifier."""

    @abstractmethod
    def put_file(self, bucket: str, key: str, path: str, content_type: str = "application/octet-stream") -> str:
        """Store a local file; return a storage key/path identifier."""

    @abstractmethod
    def get(self, bucket: str, key: str) -> bytes:
        """Read object bytes."""

    @abstractmethod
    def download_to_file(self, bucket: str, key: str, dest_path: str) -> str:
        """Stream object to a local file; return the destination path."""

    @abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        """Delete an object if it exists."""

    @abstractmethod
    def exists(self, bucket: str, key: str) -> bool:
        """Whether an object exists."""

    @abstractmethod
    def signed_download_url(self, bucket: str, key: str, expires_seconds: int) -> str:
        """Return a (possibly backend-side) signed URL or a token to validate server-side."""
