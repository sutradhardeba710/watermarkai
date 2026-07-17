"""Shared worker utilities: per-job locking, heartbeat, tempdir isolation.

SRS WORKER-001..007, REL-001..006.
"""
from __future__ import annotations

import contextlib
import tempfile
import time
import uuid
from pathlib import Path
from typing import Generator

import redis
from celery import current_task

from app.core.config import get_settings

settings = get_settings()


def _redis() -> redis.Redis:
    return redis.from_url(settings.redis_url)


@contextlib.contextmanager
def job_lock(job_id: str, worker_id: str, ttl_seconds: int = 600) -> Generator[bool, None, None]:
    """Redis SETNX job lock — one worker per job (WORKER-004)."""
    r = _redis()
    key = f"job_lock:{job_id}"
    acquired = r.set(key, worker_id, nx=True, ex=ttl_seconds)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            # only delete if we still own it
            current = r.get(key)
            if current and current.decode() == worker_id:
                r.delete(key)


@contextlib.contextmanager
def isolated_tempdir(prefix: str = "vwa-") -> Generator[Path, None, None]:
    """WORKER-005: isolated temp dir, cleaned up on exit even on failure."""
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        import shutil

        shutil.rmtree(d, ignore_errors=True)


def worker_id() -> str:
    return f"{current_task.request.hostname}-{uuid.uuid4().hex[:8]}" if current_task and current_task.request else "cli"


def heartbeat(worker_name: str) -> None:
    """WORKER-003: stamp a heartbeat key the admin monitor reads."""
    r = _redis()
    r.hset("workers:heartbeat", worker_name, str(int(time.time())))
    r.expire("workers:heartbeat", 120)
