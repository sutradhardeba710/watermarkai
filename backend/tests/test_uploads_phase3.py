"""Phase 3 pure-logic tests (SRS UPLOAD, META, NORM, LEGAL, SEC-004/007).

Only exercise functions that do not require ffmpeg / opencv / sqlalchemy /
fastapi — they run on the 32-bit dev box. Online integration (probe_container,
run_ffmpeg, the routes themselves) is verified manually on a 64-bit env.
"""
from __future__ import annotations

import os

import pytest

from app.services import compliance, normalize, validation


# --- Filename sanitization (SEC-007) ---


def test_sanitize_filename_strips_path_traversal():
    assert validation.sanitize_filename("../evil.mp4") == "evil.mp4"
    assert validation.sanitize_filename("..\\evil.mp4") == "evil.mp4"
    assert validation.sanitize_filename("../../../etc/passwd.mp4") == "passwd.mp4"


def test_sanitize_filename_strips_leading_dots_and_spaces():
    assert validation.sanitize_filename("  .hidden.mp4 ") == "hidden.mp4"


def test_sanitize_filename_replaces_control_chars():
    # semicolons, pipes can leak into shell contexts — replaced with underscore
    assert validation.sanitize_filename("bad;name|rm.mp4") == "bad_name_rm.mp4"


def test_sanitize_filename_rejects_empty_after_strip():
    from app.core.errors import AppError
    with pytest.raises(AppError):
        validation.sanitize_filename("")
    with pytest.raises(AppError):
        validation.sanitize_filename(".")
    with pytest.raises(AppError):
        validation.sanitize_filename("..")


# --- Extension allowlist ---


def test_validate_extension_accepts_whitelisted():
    for name in ["clip.mp4", "Clip.MP4", "a.mov", "b.webm"]:
        v = validation.validate_extension(name, allowed=["mp4", "mov", "webm"])
        assert v.ok, v.message


def test_validate_extension_rejects_unknown():
    v = validation.validate_extension("foo.mkv", allowed=["mp4", "mov", "webm"])
    assert not v.ok
    assert v.code == "UNSUPPORTED_FORMAT"


def test_validate_extension_rejects_executable_disguise():
    # Even if .exe somehow lands in the allowlist, the executable guard trips.
    v = validation.validate_extension("malware.exe", allowed=["exe"])
    assert not v.ok
    assert v.code == "UNSUPPORTED_FORMAT"


def test_validate_extension_rejects_no_extension():
    v = validation.validate_extension("noext", allowed=["mp4"])
    assert not v.ok
    assert v.code == "UNSUPPORTED_FORMAT"


# --- MIME sniff (SEC-004) ---


def test_sniff_mime_detects_mp4_ftyp():
    head = b"\x00\x00\x00\x18ftypmp42"
    assert validation.sniff_mime(head) == "mp4"


def test_sniff_mime_detects_webm_ebml():
    head = b"\x1a\x45\xdf\xa3" + b"\x00" * 8
    assert validation.sniff_mime(head) == "webm"


def test_sniff_mime_rejects_random_bytes():
    assert validation.sniff_mime(b"lorem ipsum dolor") is None


def test_validate_mime_passes_when_declared_matches_sniff():
    head = b"\x00\x00\x00\x18ftypmp42"
    v = validation.validate_mime(head, "video/mp4")
    assert v.ok


def test_validate_mime_rejects_declared_vs_sniffed_mismatch():
    head = b"\x00\x00\x00\x18ftypmp42"
    v = validation.validate_mime(head, "video/webm")
    assert not v.ok
    assert v.code == "UNSUPPORTED_FORMAT"


# --- Size validation ---


def test_validate_size_rejects_over_limit():
    v = validation.validate_size(2 * 1024 * 1024, max_mb=1)
    assert not v.ok
    assert v.code == "FILE_TOO_LARGE"


def test_validate_size_rejects_zero_or_negative():
    v = validation.validate_size(0)
    assert not v.ok
    v = validation.validate_size(-1)
    assert not v.ok


def test_validate_size_accepts_unknown():
    v = validation.validate_size(None)
    assert v.ok


# --- ffprobe JSON parsing (META-001/003) ---


MP4_PROBE = """
{
  "streams": [
    {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
     "avg_frame_rate": "30000/1001", "nb_frames": "9000", "duration": "300.3"},
    {"codec_type": "audio", "codec_name": "aac", "duration": "300.3"}
  ],
  "format": {"duration": "300.3", "bit_rate": "1500000", "format_name": "mov,mp4,m4a"}
}
"""


def test_parse_ffprobe_json_normalises_fields():
    meta = validation.parse_ffprobe_json(MP4_PROBE)
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["video_codec"] == "h264"
    assert meta["audio_codec"] == "aac"
    assert meta["has_audio"] is True
    assert meta["frame_count"] == 9000
    assert abs(meta["fps"] - 29.97) < 0.01


def test_parse_ffprobe_json_rejects_missing_video_stream():
    from app.core.errors import AppError
    audio_only = '{"streams": [{"codec_type": "audio", "codec_name": "aac"}], "format": {}}'
    with pytest.raises(AppError) as exc:
        validation.parse_ffprobe_json(audio_only)
    assert exc.value.code == "UNSUPPORTED_FORMAT"


def test_parse_ffprobe_json_rejects_non_json():
    from app.core.errors import AppError
    with pytest.raises(AppError) as exc:
        validation.parse_ffprobe_json("not json at all")
    assert exc.value.code == "METADATA_ERROR"


def test_parse_fps_handles_fraction_strings():
    assert abs(validation._parse_fps("30000/1001") - 29.97) < 0.01
    assert validation._parse_fps("0/0") is None
    assert validation._parse_fps(None) is None
    assert validation._parse_fps("30") == 30.0


# --- Limit enforcement (NORM / UPLOAD limits) ---


def test_enforce_limits_accepts_under_caps():
    from app.core.config import Settings

    s = Settings()
    meta = {"duration": 60, "width": 1280, "height": 720, "fps": 30}
    v = validation.enforce_limits(meta, s)
    assert v.ok


def test_enforce_limits_rejects_too_long():
    from app.core.config import Settings

    s = Settings()
    meta = {"duration": s.max_duration_seconds + 1, "width": 640, "height": 360, "fps": 30}
    v = validation.enforce_limits(meta, s)
    assert not v.ok
    assert v.code == "DURATION_TOO_LONG"


def test_enforce_limits_rejects_too_tall():
    from app.core.config import Settings

    s = Settings()
    meta = {"duration": 10, "width": 1920, "height": s.max_height + 1, "fps": 30}
    v = validation.enforce_limits(meta, s)
    assert not v.ok
    assert v.code == "RESOLUTION_TOO_HIGH"


def test_enforce_limits_rejects_too_fast():
    from app.core.config import Settings

    s = Settings()
    meta = {"duration": 10, "width": 640, "height": 360, "fps": float(s.max_fps + 1)}
    v = validation.enforce_limits(meta, s)
    assert not v.ok
    assert v.code == "FPS_TOO_HIGH"


# --- FFmpeg arg building (SEC-007: arg-list only, no shell) ---


def test_proxy_args_downscales_to_720p_and_hardcaps_one_arg_per_flag():
    args = normalize.proxy_args("in.mp4", "out.mp4")
    assert args[0].endswith("ffmpeg") or args[0] == "ffmpeg"
    # Each input/value is its own list entry — no shell-concatenated "|;&&" tokens.
    assert all(" " not in a for a in args)
    assert "-vf" in args and f"scale=-2:720" in args
    assert "-pix_fmt" in args and "yuv420p" in args
    assert "-movflags" in args and "+faststart" in args
    assert args[-1] == "out.mp4"
    assert args[args.index("-i") + 1] == "in.mp4"


def test_split_audio_args_no_video_stream():
    args = normalize.split_audio_args("in.mp4", "audio.aac")
    assert "-vn" in args
    assert "-c:a" in args and "copy" in args
    assert "-map" in args
    assert args[args.index("-i") + 1] == "in.mp4"


def test_thumbnail_args_grabs_single_frame():
    args = normalize.thumbnail_args("in.mp4", "thumb.jpg", at_seconds=2.5)
    assert "-frames:v" in args and "1" in args
    assert "-ss" in args and args[args.index("-ss") + 1] == "2.5"
    assert args[-1] == "thumb.jpg"


# --- Legal gating (LEGAL-002/003) ---


def test_gate_unconfirmed_raises():
    from app.core.errors import AppError
    with pytest.raises(AppError) as exc:
        compliance.gate_unconfirmed(False)
    assert exc.value.status_code == 403
    assert exc.value.code == "LEGAL_CONFIRMATION_REQUIRED"


def test_gate_unconfirmed_passes_when_confirmed():
    compliance.gate_unconfirmed(True)


def test_hash_ip_is_salted_and_stable():
    a = compliance.hash_ip("1.2.3.4")
    b = compliance.hash_ip("1.2.3.4")
    assert a == b and a is not None and len(a) == 64
    c = compliance.hash_ip("5.6.7.8")
    assert a != c


def test_hash_ip_handles_none():
    assert compliance.hash_ip(None) is None
    assert compliance.hash_ip("") is None


def test_summarize_ua_buckets_common_combos():
    assert compliance.summarize_ua("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit Chrome/120") == "chrome/windows"
    assert compliance.summarize_ua("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit Safari/605") == "safari/mac"
    assert compliance.summarize_ua("Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Firefox/121") == "firefox/linux"
    assert compliance.summarize_ua("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari") == "safari/ios"
    assert compliance.summarize_ua(None) is None


# --- Duplicate-prevention hash (UPLOAD-006) ---


def test_hash_head_matches_identical_content(tmp_path):
    f1 = tmp_path / "a.mp4"
    f2 = tmp_path / "b.mp4"
    f1.write_bytes(b"identical" * 100000)
    f2.write_bytes(b"identical" * 100000)
    assert validation.hash_head(f1) == validation.hash_head(f2)


def test_hash_head_differs_for_different_content(tmp_path):
    f1 = tmp_path / "a.mp4"
    f2 = tmp_path / "b.mp4"
    f1.write_bytes(b"prefix-A" + b"x" * 100000)
    f2.write_bytes(b"prefix-B" + b"x" * 100000)
    assert validation.hash_head(f1) != validation.hash_head(f2)
