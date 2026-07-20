"""FFmpeg encode/decode arg builders for the processing pipeline (SRS ENCODE-001..007).

Pure argument-list builders so the shapes are unit-testable without ffmpeg on
PATH (the dev box only has 32-bit Python). :func:`run_ffmpeg` reuses the
existing executor in :mod:`app.services.normalize` and is the single shell-out.

Pipeline steps built here:
  * extract_frames_args  — source -> numbered PNG frames at original FPS (WORKER-005)
  * encode_args          — frames dir + remuxed audio -> H.264 yuv420p output,
                           preserving A/V sync + FPS (ENCODE-003/004)
  * remux_audio_args     — demux original audio to disk for remux fallback (NORM-003)
  * validate_output_args — ffprobe arg list verifying the encoded output is playable
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def extract_frames_args(src: str | Path, frames_dir: str | Path, fps: float | None = None) -> list[str]:
    """FFmpeg arg list to extract every frame to `<frames_dir>/frame_%08d.png`.

    Uses the source's own frame rate when fps is None (pass-through) so the
    frame count matches `nb_frames` from the probe. PNG is lossless so the
    inpaint step never re-compresses.
    """
    settings = get_settings()
    vf = f"fps={fps}" if fps else "null"
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vf", vf,
        "-vsync", "0",          # passthrough — keeps every frame
        # NOTE: no -frame_pts — the encode step reads the frames back with the
        # image2 sequence demuxer, which requires sequential numbering starting
        # near 0. PTS-derived names (e.g. an MP4 edit-list start offset, or raw
        # 512-step stream PTS when fps is None) leave gaps that truncate or
        # fail the encode.
        str(Path(frames_dir) / "frame_%08d.png"),
    ]


def remux_audio_args(src: str | Path, dst_audio: str | Path) -> list[str]:
    """Demux the original audio track losslessly to disk (NORM-003). No-op if the
    source has no audio (FFmpeg exits non-zero; callers fall back to no-audio mux).

    Only works when the source audio is already AAC (the raw ``.aac`` ADTS
    container accepts nothing else) — for Vorbis/Opus/PCM sources callers fall
    back to :func:`transcode_audio_aac_args`.
    """
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vn",
        "-map", "a?",
        "-c:a", "copy",
        "-sn",
        str(dst_audio),
    ]


def transcode_audio_aac_args(src: str | Path, dst_audio: str | Path, *, bitrate: str = "192k") -> list[str]:
    """Re-encode the source audio to AAC (ENCODE-004 fallback).

    Used when the original codec can't be copied into the .aac/.mp4 container
    (webm's Vorbis/Opus, MOV PCM). Without this fallback every such upload
    silently produced a silent output.
    """
    settings = get_settings()
    return [
        settings.ffmpeg_bin,
        "-y",
        "-i", str(src),
        "-vn",
        "-map", "a?",
        "-c:a", "aac",
        "-b:a", bitrate,
        "-sn",
        str(dst_audio),
    ]


def encode_args(
    frames_dir: str | Path,
    dst: str | Path,
    *,
    fps: float,
    audio_path: str | Path | None = None,
    audio_codec: str = "copy",
    width: int | None = None,
    height: int | None = None,
    output_codec: str | None = None,
    pixel_format: str | None = None,
    crf: int = 20,
    preset: str = "medium",
) -> list[str]:
    """FFmpeg arg list: frames dir -> H.264 yuv420p MP4, remuxing original audio.

    ENCODE-003: `-r <fps>` on the input sets the frame rate so A/V stays in sync
    when audio is muxed back in. ENCODE-004: original audio is copied losslessly
    by default; callers switch audio_codec to `aac` if the codec is incompatible
    with MP4 (e.g. Vorbis/Opus from a webm source).
    """
    settings = get_settings()
    oc = output_codec or settings.output_codec
    pf = pixel_format or settings.output_pixel_format

    vf_parts: list[str] = []
    if width and height:
        vf_parts.append(f"scale={width}:{height}")
    vf = ",".join(vf_parts) or "null"

    args = [
        settings.ffmpeg_bin,
        "-y",
        "-framerate", f"{fps}",
        "-i", str(Path(frames_dir) / "frame_%08d.png"),
    ]
    if audio_path is not None:
        args += ["-i", str(audio_path)]
    args += [
        "-vf", vf,
        "-c:v", oc,
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", pf,
        "-r", f"{fps}",             # ENCODE-003: keep presentation fps
        "-movflags", "+faststart",
    ]
    if audio_path is not None:
        args += ["-c:a", audio_codec, "-shortest"]
    else:
        args += ["-an"]             # no audio: explicit an to keep mux clean
    args.append(str(dst))
    return args


def validate_output_args(path: str | Path) -> list[str]:
    """ffprobe arg list for output validation (ENCODE-007). Returns JSON the
    caller parses to assert a video stream exists, duration is within tolerance,
    and the file decodes cleanly."""
    settings = get_settings()
    return [
        settings.ffprobe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]


def output_duration_within_tolerance(
    source_duration: float | None,
    output_duration: float | None,
    *,
    tol_ms: float = 100.0,
) -> bool:
    """ENCODE-007 boundary: output duration must be within tol_ms of source.
    Unknown durations pass (the validator probes them again on a 64-bit box)."""
    if source_duration is None or output_duration is None:
        return True
    return abs(source_duration - output_duration) <= (tol_ms / 1000.0)


__all__ = [
    "extract_frames_args",
    "remux_audio_args",
    "transcode_audio_aac_args",
    "encode_args",
    "validate_output_args",
    "output_duration_within_tolerance",
]
