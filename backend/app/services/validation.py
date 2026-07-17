"""Upload validation service (SRS UPLOAD, META, NORM, SEC-004/005/007).

Pure logic lives here so the rules can be unit-tested without FFmpeg/opencv
installed (the dev box only has 32-bit Python). Anything that shells out to
ffprobe/ffmpeg is isolated in :func:`probe_container` and only invoked from the
upload-route runtime path.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import AppError

# Executable suffixes we never accept as a video upload regardless of extension.
_EXECUTABLE_SUFFIXES = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".ps1", ".vbs", ".js", ".jar",
    ".msi", ".dll", ".sh", ".app",
}

# First-byte signatures for the whitelisted containers (MIME sniff, SRS SEC-004).
# MP4/MOV is detected by the 'ftyp' box at offset 4 rather than a fixed magic.


@dataclass
class ValidationResult:
    ok: bool
    code: str = "OK"
    message: str = ""
    file_size: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def sanitize_filename(raw: str) -> str:
    """Return a safe basename. Strips path separators, drops traversal, length-limits.

    SEC-007: never shell-concat user input; this is applied before any storage
    key or ffprobe argument is built.
    """
    # Take only the basename portion so '../../foo.mp4' cannot escape.
    base = os.path.basename(raw.replace("\\", "/"))
    if not base or base in {".", ".."}:
        raise AppError("VALIDATION_ERROR", "Invalid filename.", 422)
    # Strip control chars and anything that is not printable ASCII / common Unicode letters.
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE)
    base = base.strip(" .")  # no leading dots/spaces (hidefiles on *nix)
    if not base:
        raise AppError("VALIDATION_ERROR", "Invalid filename.", 422)
    return base[:512]


def file_extension(filename: str) -> str:
    """Lowercase extension without the dot. '' if none."""
    _, ext = os.path.splitext(filename)
    return ext[1:].lower()


def validate_extension(filename: str, allowed: list[str] | None = None) -> ValidationResult:
    settings = get_settings()
    allow = allowed or settings.allowed_upload_extensions
    ext = file_extension(filename)
    if not ext:
        return ValidationResult(False, "UNSUPPORTED_FORMAT", "File has no extension.")
    if ext not in allow:
        return ValidationResult(
            False,
            "UNSUPPORTED_FORMAT",
            f"Extension '.{ext}' is not allowed. Allowed: {', '.join(sorted(allow))}.",
        )
    lowered = filename.lower()
    if any(lowered.endswith(suf) for suf in _EXECUTABLE_SUFFIXES):
        return ValidationResult(
            False, "UNSUPPORTED_FORMAT", "Executable files are not allowed."
        )
    return ValidationResult(ok=True, details={"extension": ext})


def sniff_mime(head: bytes) -> str | None:
    """Map leading file bytes to a container family, or None if unknown.

    Used for SEC-004 content sniffing — the extension whitelist alone is not
    trusted.
    """
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    # MP4/MOV: bytes 4-7 are 'ftyp'
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4"
    return None


def validate_mime(
    head: bytes, declared_mime: str | None, allowed_mime: list[str] | None = None
) -> ValidationResult:
    settings = get_settings()
    allowed = allowed_mime or settings.allowed_upload_mime
    sniffed = sniff_mime(head)
    if sniffed is None:
        return ValidationResult(False, "UNSUPPORTED_FORMAT", "File does not look like a supported video container.")
    expected = {
        "mp4": "video/mp4",
        "webm": "video/webm",
    }.get(sniffed)
    if expected and expected not in allowed:
        return ValidationResult(False, "UNSUPPORTED_FORMAT", f"Container '{sniffed}' is not in the allowlist.")
    # If the client declared a MIME, it must match the sniffed container family.
    if declared_mime:
        declared = declared_mime.split(";")[0].strip().lower()
        if declared != expected:
            return ValidationResult(
                False,
                "UNSUPPORTED_FORMAT",
                f"Declared MIME '{declared}' disagrees with sniffed '{expected}'.",
            )
    return ValidationResult(ok=True, details={"sniffed_container": sniffed})


def validate_size(file_size: int | None, max_mb: int | None = None) -> ValidationResult:
    settings = get_settings()
    cap = max_mb if max_mb is not None else settings.max_file_size_mb
    if file_size is None:
        # Unknown yet (chunked POST); defer to post-upload check.
        return ValidationResult(ok=True)
    if file_size <= 0:
        return ValidationResult(False, "VALIDATION_ERROR", "File is empty.")
    if file_size > cap * 1024 * 1024:
        return ValidationResult(
            False, "FILE_TOO_LARGE", f"File exceeds the {cap} MB upload limit.", {"max_bytes": cap * 1024 * 1024}
        )
    return ValidationResult(ok=True, file_size=file_size)


def parse_ffprobe_json(stdout: str) -> dict[str, Any]:
    """Parse `ffprobe -print_format json` output into a normalised dict.

    Pure function — never shells out. Raises :class:`AppError` if the JSON is
    missing or the stream layout is unsupported (META-003).
    """
    import json

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AppError("METADATA_ERROR", "ffprobe returned non-JSON output.", 502) from exc

    if "streams" not in data:
        raise AppError("METADATA_ERROR", "ffprobe output is missing streams.", 502)

    streams = data["streams"]
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise AppError("UNSUPPORTED_FORMAT", "No video stream found in file.", 415)

    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    meta = data.get("format", {})

    def _f(value: Any, conv=float) -> float | None:
        try:
            return conv(value) if value not in (None, "N/A") else None
        except (TypeError, ValueError):
            return None

    return {
        "duration": _f(video.get("duration")) or _f(meta.get("duration")) or 0.0,
        "width": _f(video.get("width"), int),
        "height": _f(video.get("height"), int),
        "fps": _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "frame_count": _f(video.get("nb_frames"), int),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "has_audio": audio is not None,
        "container": meta.get("format_name"),
        "bit_rate": _f(meta.get("bit_rate"), int),
        "raw": data,
    }


_FPS_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def _parse_fps(expr: str | None) -> float | None:
    if not expr or expr == "0/0":
        return None
    m = _FPS_RE.match(expr)
    if m:
        denom = int(m.group(2))
        if denom:
            return int(m.group(1)) / denom
    try:
        return float(expr)
    except ValueError:
        return None


def enforce_limits(meta: dict[str, Any], settings=None) -> ValidationResult:
    """Apply duration / resolution / FPS caps (NORM / UPLOAD limits).

    Returns a :class:`ValidationResult`; failures carry the offending limit so
    the route can surface it via the BE-004 envelope.
    """
    settings = settings or get_settings()
    duration = meta.get("duration") or 0.0
    if duration > settings.max_duration_seconds:
        return ValidationResult(
            False, "DURATION_TOO_LONG",
            f"Video is {duration:.1f}s; max is {settings.max_duration_seconds}s.",
            {"max_duration_seconds": settings.max_duration_seconds},
        )
    width = meta.get("width") or 0
    height = meta.get("height") or 0
    if width > settings.max_width or height > settings.max_height:
        return ValidationResult(
            False, "RESOLUTION_TOO_HIGH",
            f"Video is {width}x{height}; max is {settings.max_width}x{settings.max_height}.",
            {"max_width": settings.max_width, "max_height": settings.max_height},
        )
    fps = meta.get("fps") or 0.0
    if fps > settings.max_fps:
        return ValidationResult(
            False, "FPS_TOO_HIGH",
            f"Video is {fps:.1f}fps; max is {settings.max_fps}fps.",
            {"max_fps": settings.max_fps},
        )
    return ValidationResult(ok=True)


def probe_container(path: str | Path) -> dict[str, Any]:
    """Run ffprobe over a local file, returning normalised metadata.

    SEC-007: subprocess arg-list only — never shell=True, never string-concat.
    Raises :class:`AppError` on non-zero exit or missing binary.
    """
    settings = get_settings()
    args = [
        settings.ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError as exc:
        raise AppError("METADATA_ERROR", "ffprobe binary not found on PATH.", 502) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError("METADATA_ERROR", "ffprobe timed out inspecting the file.", 504) from exc
    if proc.returncode != 0:
        raise AppError("METADATA_ERROR", f"ffprobe failed: {proc.stderr.strip()}", 415)
    return parse_ffprobe_json(proc.stdout)


def hash_head(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    """SHA-256 over the first chunk of a file (UPLOAD-006 duplicate warning)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(chunk_bytes))
    return h.hexdigest()


__all__ = [
    "ValidationResult",
    "sanitize_filename",
    "file_extension",
    "validate_extension",
    "sniff_mime",
    "validate_mime",
    "validate_size",
    "parse_ffprobe_json",
    "enforce_limits",
    "probe_container",
    "hash_head",
]
