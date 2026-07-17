"""Normalization / proxy generation service (SRS NORM-001..004).

Builds an FFmpeg argument list (SEC-007: arg-list only, no shell) for the proxy
transcode and for separating the original audio track. The pure argument
builders are unit-testable without ffmpeg on PATH.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError

# Proxy caps (NORM-001): downscale to <=720p high, keep original FPS.
_PROXY_MAX_HEIGHT = 720
_PROXY_CRF = 23
_PROXY_PRESET = "veryfast"


def proxy_args(src: str | Path, dst: str | Path, max_height: int = _PROXY_MAX_HEIGHT) -> list[str]:
    """FFmpeg arg list to render a <=720p H.264 proxy of the source."""
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vf", f"scale=-2:{max_height}",
        "-c:v", settings.output_codec,
        "-crf", str(_PROXY_CRF),
        "-preset", _PROXY_PRESET,
        "-pix_fmt", settings.output_pixel_format,
        "-c:a", "aac",        # proxy re-encodes audio to be broadly playable
        "-movflags", "+faststart",
        str(dst),
    ]


def split_audio_args(src: str | Path, dst_audio: str | Path) -> list[str]:
    """FFmpeg arg list to demux the original audio track to disk (NORM-003)."""
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vn",            # no video
        "-c:a", "copy",   # preserve original codec
        "-map", "a?",
        str(dst_audio),
    ]


def thumbnail_args(src: str | Path, dst: str | Path, at_seconds: float = 1.0) -> list[str]:
    """FFmpeg arg list to grab a single JPEG thumbnail near the start."""
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-ss", f"{at_seconds}",
        "-i", str(src),
        "-frames:v", "1",
        "-vf", "scale=640:-2",
        str(dst),
    ]


def run_ffmpeg(args: list[str]) -> None:
    """Execute an FFmpeg arg list built by the helpers above.

    Raises :class:`AppError` on non-zero exit / missing binary / timeout so the
    route can surface it via the BE-004 envelope.
    """
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600, check=False)
    except FileNotFoundError as exc:
        raise AppError("NORMALIZE_ERROR", "ffmpeg binary not found on PATH.", 502) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError("NORMALIZE_ERROR", "ffmpeg timed out during proxy generation.", 504) from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise AppError("NORMALIZE_ERROR", "ffmpeg failed: " + " | ".join(tail), 502)


__all__ = ["proxy_args", "split_audio_args", "thumbnail_args", "run_ffmpeg"]
