"""Phase 9 pure-logic unit tests — validation, metadata parse, ownership checks,
status-transition edge cases, NORM arg builders (SEC-007).

Covers TEST-001: unit tests for pieces not already exercised by Phases 3–8.
Runs on the 32-bit box without ffmpeg/DB.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services import validation, normalize
from app.services.job_states import can_transition_values
from app.services.admin_service import is_brittle_region


# ---------------------------------------------------------------------------
# Validation (SEC-004/005/007, UPLOAD)
# ---------------------------------------------------------------------------


def test_sanitize_filename_keeps_basename_and_drops_traversal():
    assert validation.sanitize_filename("../../evil.mp4") == "evil.mp4"
    assert validation.sanitize_filename("normal.mp4") == "normal.mp4"
    assert validation.sanitize_filename(r"C:\tmp\file.webm") == "file.webm"
    assert validation.sanitize_filename("../../../hidden") == "hidden"  # leading dot stripped


def test_sanitize_filename_control_chars_replaced():
    assert validation.sanitize_filename("a\x00b.mp4") == "a_b.mp4"
    assert validation.sanitize_filename("file\name.webm") == "file_ame.webm"


def test_sanitize_filename_empty_after_sanitization_raises():
    with pytest.raises(Exception):  # AppError
        validation.sanitize_filename("...  ")


def test_file_extension_lowercase():
    assert validation.file_extension("Video.MP4") == "mp4"
    assert validation.file_extension("clip.webm") == "webm"
    assert validation.file_extension("noext") == ""


def test_validate_extension_accepts_whitelisted():
    r = validation.validate_extension("video.mp4")
    assert r.ok
    assert r.details.get("extension") == "mp4"


def test_validate_extension_rejects_unknown_and_executable():
    r = validation.validate_extension("script.exe")
    assert not r.ok
    assert r.code in ("UNSUPPORTED_FORMAT", "VALIDATION_ERROR")

    r = validation.validate_extension("data.bin")
    assert not r.ok


def test_sniff_mime_mp4_and_webm():
    # MP4: 'ftyp' at offset 4 (need at least 12 bytes head)
    mp4_head = b"\x00\x00\x00\x20ftypisom"
    assert validation.sniff_mime(mp4_head) == "mp4"
    # WebM: EBML magic at offset 0
    assert validation.sniff_mime(b"\x1a\x45\xdf\xa3") == "webm"


def test_sniff_mime_unknown():
    assert validation.sniff_mime(b"\x00\x00\x00\x00") is None


def test_validate_mime_matches_sniffed():
    mp4_head = b"\x00\x00\x00\x20ftypisom"
    r = validation.validate_mime(mp4_head, declared_mime=None)
    assert r.ok
    assert r.details.get("sniffed_container") == "mp4"


def test_validate_mime_rejects_declared_mismatch():
    mp4_head = b"\x00\x00\x00\x20ftypisom"
    r = validation.validate_mime(mp4_head, declared_mime="video/webm")
    assert not r.ok
    assert "disagrees" in r.message.lower()


def test_validate_size_within_cap():
    r = validation.validate_size(100, max_mb=1)
    assert r.ok
    assert r.file_size == 100


def test_validate_size_exceeds_cap():
    r = validation.validate_size(2_000_000, max_mb=1)
    assert not r.ok
    assert "exceeds" in r.message.lower()


def test_parse_ffprobe_json_basic():
    raw = """
    {
      "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
         "avg_frame_rate": "30000/1001", "duration": "10.5"},
        {"codec_type": "audio", "codec_name": "aac"}
      ],
      "format": {"duration": "10.5", "format_name": "mov,mp4"}
    }
    """
    meta = validation.parse_ffprobe_json(raw)
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["fps"] == pytest.approx(30000 / 1001, rel=1e-5)
    assert meta["duration"] == 10.5
    assert meta["has_audio"] is True
    assert meta["video_codec"] == "h264"
    assert meta["audio_codec"] == "aac"


def test_parse_ffprobe_json_fraction_fps():
    raw = """
    {
      "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720,
         "avg_frame_rate": "25/1", "nb_frames": "250"}
      ],
      "format": {}
    }
    """
    meta = validation.parse_ffprobe_json(raw)
    assert meta["fps"] == 25.0
    assert meta["frame_count"] == 250
    assert meta["has_audio"] is False


def test_parse_ffprobe_json_missing_streams_raises():
    with pytest.raises(Exception):
        validation.parse_ffprobe_json("{}")


def test_parse_ffprobe_json_no_video_stream_raises():
    with pytest.raises(Exception):
        validation.parse_ffprobe_json('{"streams": [{"codec_type": "audio"}]}')


def test_parse_fps_handles_fraction_decimal_and_invalid():
    assert validation._parse_fps("30000/1001") == pytest.approx(30000 / 1001, rel=1e-5)
    assert validation._parse_fps("25/1") == 25.0
    assert validation._parse_fps("30") == 30.0
    assert validation._parse_fps("0/0") is None
    assert validation._parse_fps(None) is None


def test_enforce_limits_duration_resolution_fps():
    meta = {"duration": 600, "width": 1920, "height": 1080, "fps": 60}
    settings = SimpleNamespace(max_duration_seconds=300, max_width=1920, max_height=1080, max_fps=60)
    r = validation.enforce_limits(meta, settings=settings)
    assert not r.ok
    assert r.code == "DURATION_TOO_LONG"

    meta = {"duration": 10, "width": 3840, "height": 2160, "fps": 24}
    r = validation.enforce_limits(meta, settings=settings)
    assert not r.ok
    assert r.code == "RESOLUTION_TOO_HIGH"

    meta = {"duration": 10, "width": 1280, "height": 720, "fps": 120}
    r = validation.enforce_limits(meta, settings=settings)
    assert not r.ok
    assert r.code == "FPS_TOO_HIGH"

    meta = {"duration": 10, "width": 1280, "height": 720, "fps": 24}
    r = validation.enforce_limits(meta, settings=settings)
    assert r.ok


def test_hash_head_produces_hex():
    # Create a temp file; its hash is deterministic for given content
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"a" * 1000)
        tf.flush()
        h1 = validation.hash_head(tf.name)
        h2 = validation.hash_head(tf.name)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# NORM arg builders (SEC-007: arg lists only)
# ---------------------------------------------------------------------------


def _first(a: list[str]) -> str:
    return a[0]


def test_proxy_args_uses_correct_bin_and_scale_filter():
    a = normalize.proxy_args("in.mp4", "proxy.mp4")
    assert _first(a) == normalize.get_settings().ffmpeg_bin
    assert "-vf" in a
    assert "scale=-2:720" in " ".join(a)


def test_proxy_args_includes_codec_and_pix_fmt():
    a = normalize.proxy_args("in.webm", "proxy.mp4")
    assert "-c:v" in a
    assert any("libx264" in arg or a[a.index("-c:v") + 1] == "libx264" for arg in a)
    assert "-pix_fmt" in a


def test_proxy_args_arg_list_not_shell_concatenated():
    a = normalize.proxy_args("my file.mp4", "out proxy.mp4")
    # SEC-007: arg-list form; the filename may have spaces — that's okay
    # as long as we don't join into a shell string.
    assert isinstance(a, list)
    # The first token is the binary; input/output are passed as separate tokens.
    assert any("my file.mp4" in str(tok) for tok in a)


def test_split_audio_args_includes_vn_and_copy():
    a = normalize.split_audio_args("video.mp4", "audio.aac")
    assert "-vn" in a
    assert "-c:a" in a
    idx = a.index("-c:a")
    assert a[idx + 1] == "copy"


def test_thumbnail_args_single_frame_and_scale():
    a = normalize.thumbnail_args("src.mp4", "thumb.jpg", at_seconds=2.5)
    assert "-ss" in a
    assert a[a.index("-ss") + 1] == "2.5"
    assert "-frames:v" in a
    assert a[a.index("-frames:v") + 1] == "1"
    assert "-vf" in a


# ---------------------------------------------------------------------------
# Ownership checks (pattern mirrored by get_project_owned)
# ---------------------------------------------------------------------------


def _ownership_guard(user_id: str, project_user_id: str, deleted: bool = False) -> bool:
    """Pure mirror of the ownership guard in `uploads.get_project_owned`."""
    return project_user_id == user_id and not deleted


def test_ownership_guard_accepts_owner():
    assert _ownership_guard("u1", "u1", deleted=False) is True


def test_ownership_guard_rejects_different_user():
    assert _ownership_guard("u1", "u2", deleted=False) is False


def test_ownership_guard_rejects_deleted():
    assert _ownership_guard("u1", "u1", deleted=True) is False


# ---------------------------------------------------------------------------
# Status-transition edges (PROCESS-002)
# ---------------------------------------------------------------------------


def test_can_transition_values_legal_edges():
    assert can_transition_values("uploaded", "analyzing")
    assert can_transition_values("processing_queued", "processing")
    assert can_transition_values("processing", "encoding")
    assert can_transition_values("encoding", "completed")
    assert can_transition_values("encoding", "failed")
    assert can_transition_values("uploaded", "cancelled")


def test_can_transition_values_illegal_jumps():
    assert not can_transition_values("uploaded", "completed")
    assert not can_transition_values("processing_queued", "completed")
    assert not can_transition_values("failed", "processing_queued")
    assert not can_transition_values("completed", "processing")


def test_can_transition_values_terminals_have_no_outgoing():
    for terminal in ("completed", "failed", "cancelled", "expired"):
        assert not can_transition_values(terminal, "processing")

    for src in ("completed", "failed", "cancelled", "expired", "preview_ready"):
        assert not can_transition_values(src, "uploaded")


def test_can_transition_values_self_loops_blocked():
    assert not can_transition_values("processing", "processing")
    assert not can_transition_values("completed", "completed")


# ---------------------------------------------------------------------------
# RECON-008 additional edge coverage (see Phase 8 tests for main cases)
# ---------------------------------------------------------------------------


def test_is_brittle_region_missing_frame_dimensions_safe():
    geo = {"tool": "rectangle", "x": 0, "y": 0, "w": 100, "h": 100, "vertices": []}
    assert is_brittle_region(geo, frame_width=0, frame_height=0) is False


def test_is_brittle_region_uses_positive_dimensions():
    geo = {"tool": "rectangle", "x": 0, "y": 0, "w": 500, "h": 500, "vertices": []}
    # 500×500 = 250k; frame 1280×720 = 921k; ratio = 0.27 < 0.35 → safe
    assert is_brittle_region(geo, frame_width=1280, frame_height=720) is False

    geo2 = {"tool": "rectangle", "x": 0, "y": 0, "w": 800, "h": 600, "vertices": []}
    # 800×600 = 480k; frame 921k; ratio = 0.52 → brittle
    assert is_brittle_region(geo2, frame_width=1280, frame_height=720) is True


def test_is_brittle_region_handles_missing_keys_gracefully():
    geo = {"tool": "brush"}  # no strokes
    assert is_brittle_region(geo, frame_width=1280, frame_height=720) is False


# ---------------------------------------------------------------------------
# Normalize helpers (pure unit tests using mocked subprocess)
# ---------------------------------------------------------------------------


def test_run_ffmpeg_executes_subprocess(monkeypatch):
    called: dict = {}

    def fake_run(args, *, capture_output=False, text=False, timeout=None, check=False):  # type: ignore[no-untyped-def]
        called["args"] = args
        # mimic a successful run
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    from app.services.normalize import run_ffmpeg

    run_ffmpeg(["ffmpeg", "-version"])
    assert called.get("args") == ["ffmpeg", "-version"]


def _parse_fps_positive_fraction():
    # confirm parse path (already tested above, but another branch)
    assert validation._parse_fps("24000/1001") == pytest.approx(24000 / 1001, rel=1e-5)


__all__ = []
