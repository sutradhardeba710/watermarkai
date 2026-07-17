"""Preview pipeline helpers (SRS PREVIEW-001..006).

Pure FFmpeg argument builders so the windowed preview path shares shape with
the full processing pipeline (Phase 5) without re-running the whole inpaint.

  * trim_clip_args       — source -> a short windowed clip (input seeking)
  * proxy_target_args    — downscale to <=720p for the preview pass (NORM-001)
  * extract_window_frames_args / encode_preview_args frame the per-frame pass.

Helpers never shell out (SEC-007: arg lists only). The executor is the existing
:func:`run_ffmpeg` in app.services.normalize.
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def trim_clip_args(
    src: str | Path,
    dst: str | Path,
    start_seconds: float,
    duration_seconds: int,
) -> list[str]:
    """FFmpeg arg list to write a short clip of the source window to disk.

    Uses input-side `-ss` + `-t` (accurate enough after the proxy is generated)
    so the expensive seek happens before any decode. Output is copied to keep
    the preview fast when the codec is already H.264/AAC; callers re-encode only
    the per-frame inpaint pass.
    """
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-ss", f"{max(0.0, float(start_seconds)):.3f}",
        "-t", f"{int(duration_seconds)}",
        "-i", str(src),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(dst),
    ]


def proxy_target_args(src: str | Path, dst: str | Path, max_height: int = 720) -> list[str]:
    """FFmpeg arg list: source -> <=max-height H.264 proxy. The preview inpaints
    over a 720p clip rather than the full-res source to keep the loop snappy."""
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vf", f"scale=-2:{max_height}",
        "-c:v", settings.output_codec,
        "-crf", "23",
        "-preset", "veryfast",
        "-pix_fmt", settings.output_pixel_format,
        "-an",
        "-movflags", "+faststart",
        str(dst),
    ]


def extract_window_frames_args(src: str | Path, frames_dir: str | Path, fps: float | None = None) -> list[str]:
    """Same shape as the Phase 5 extractor but scoped to the trimmed clip."""
    from app.services.encode import extract_frames_args

    return extract_frames_args(src, frames_dir, fps=fps)


def encode_preview_args(
    frames_dir: str | Path,
    dst: str | Path,
    *,
    fps: float,
) -> list[str]:
    """Encode the preview frameset to H.420p without audio (preview is short)."""
    from app.services.encode import encode_args

    return encode_args(frames_dir, dst, fps=fps, audio_path=None)


def estimate_frame_count(duration_seconds: int, fps: float | None) -> int:
    """Pure helper: frames in the preview window given a source fps. Defaults to
    30 fps when unknown so progress math stays finite."""
    rate = fps if fps and fps > 0 else 30.0
    return max(1, int(round(rate * duration_seconds)))


__all__ = [
    "trim_clip_args",
    "proxy_target_args",
    "extract_window_frames_args",
    "encode_preview_args",
    "estimate_frame_count",
]
