"""Phase 5 pure-logic tests — encode arg builders, status transitions, settings
schemas, mask rebin, SSE event payload.

No DB / Redis / numpy / cv2 — runs on the 32-bit dev box. The ffmpeg arg lists
are built as plain lists so their shape is asserted without shelling out.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.services.job_states import can_transition_values
from app.schemas.processing import (
    JobEvent,
    ProcessRequest,
    ProcessSettingsRequest,
)


# ---------------------------------------------------------------------------
# Encode / decode arg builders (SRS ENCODE-001..007, SEC-007)
# ---------------------------------------------------------------------------


def _binary_first(a: list[str]) -> str:
    return a[0]


def test_extract_frames_uses_arg_list_and_png_pattern():
    from app.services import encode as enc

    a = enc.extract_frames_args("in.mp4", "frames")
    assert _binary_first(a) == enc.get_settings().ffmpeg_bin
    assert "-y" in a
    assert "-i" in a
    assert "-vsync" in a and "0" in a
    assert any(str(p).endswith("frame_%08d.png") for p in a)
    # SEC-007: every token is a single shell argument (no embedded spaces)
    for tok in a:
        assert " " not in str(tok)


def test_extract_frames_with_fps_filter():
    from app.services import encode as enc

    a = enc.extract_frames_args("in.mp4", "frames", fps=25.0)
    vf = a[a.index("-vf") + 1]
    assert vf == "fps=25.0"


def test_extract_frames_pass_through_when_no_fps():
    from app.services import encode as enc

    a = enc.extract_frames_args("in.mp4", "frames")
    assert a[a.index("-vf") + 1] == "null"


def test_encode_args_includes_libx264_and_yuv420p():
    from app.services import encode as enc
    from app.core.config import get_settings

    # With audio remux: codec copy, libx264, yuv420p, fps on both axes.
    a = enc.encode_args("frames", "out.mp4", fps=30.0, audio_path="audio.aac")
    s = get_settings()
    assert a[a.index("-c:v") + 1] == s.output_codec
    assert a[a.index("-pix_fmt") + 1] == s.output_pixel_format
    assert a[a.index("-c:a") + 1] == "copy"
    # ENCODE-003: fps stamped on input + output for A/V sync
    assert a[a.index("-framerate") + 1] == "30.0"
    assert a[a.index("-r") + 1] == "30.0"


def test_encode_args_no_audio_when_path_missing():
    from app.services import encode as enc

    a = enc.encode_args("frames", "out.mp4", fps=30.0, audio_path=None)
    assert "-an" in a
    # audio codec omitted entirely when there is no audio stream to mux
    assert "-c:a" not in a


def test_encode_args_scale_filter_shape():
    from app.services import encode as enc

    a = enc.encode_args("frames", "out.mp4", fps=30.0, width=1280, height=720)
    vf = a[a.index("-vf") + 1]
    assert vf == "scale=1280:720"


def test_encode_args_faststart_and_shortest_with_audio():
    from app.services import encode as enc

    a = enc.encode_args("frames", "out.mp4", fps=24, audio_path="audio.aac")
    assert "+faststart" in a
    assert "-shortest" in a


def test_remux_audio_arg_shape():
    from app.services import encode as enc

    a = enc.remux_audio_args("in.mp4", "audio.aac")
    assert "-vn" in a
    assert a[a.index("-c:a") + 1] == "copy"


def test_validate_output_args_json():
    from app.services import encode as enc

    a = enc.validate_output_args("out.mp4")
    assert a[a.index("-print_format") + 1] == "json"
    assert "-show_streams" in a and "-show_format" in a


# ---------------------------------------------------------------------------
# ENCODE-007 duration tolerance
# ---------------------------------------------------------------------------


def test_duration_within_tolerance_passes_on_close():
    from app.services import encode as enc

    assert enc.output_duration_within_tolerance(15.000, 15.050, tol_ms=100)
    assert enc.output_duration_within_tolerance(15.000, 15.150, tol_ms=100) is False


def test_duration_tolerance_none_passes():
    from app.services import encode as enc

    assert enc.output_duration_within_tolerance(None, 15.0)
    assert enc.output_duration_within_tolerance(15.0, None)


# ---------------------------------------------------------------------------
# PROCESS-002 status transitions
# ---------------------------------------------------------------------------


def test_transition_table_legal_path():
    assert can_transition_values("created", "processing_queued")
    assert can_transition_values("processing_queued", "processing")
    assert can_transition_values("processing", "encoding")
    assert can_transition_values("encoding", "completed")


def test_transition_table_rejects_back_edges():
    assert not can_transition_values("completed", "processing")
    assert not can_transition_values("failed", "processing")
    assert not can_transition_values("processing", "processing_queued")


def test_transition_table_rejects_skips():
    assert not can_transition_values("created", "encoding")
    assert not can_transition_values("processing_queued", "completed")


def test_transition_terminal_states_have_no_outgoing():
    for terminal in ("completed", "failed", "cancelled", "expired"):
        for target in ("created", "processing", "encoding", "completed", "processing_queued"):
            assert not can_transition_values(terminal, target)


def test_transition_idempotent_same_state_is_noop_guard():
    # No state has itself as a legal target (self-loops blocked).
    for s in ("created", "processing_queued", "processing", "encoding",
              "completed", "failed", "cancelled", "expired"):
        assert not can_transition_values(s, s)


# ---------------------------------------------------------------------------
# Settings / request schemas (PROCESS settings)
# ---------------------------------------------------------------------------


def test_process_request_default_settings_are_balanced():
    b = ProcessRequest()
    assert b.settings.quality_mode == "balanced"
    assert b.settings.preserve_audio is True


def test_settings_request_rejects_bad_quality():
    with pytest.raises(ValidationError):
        ProcessSettingsRequest(quality_mode="ultra")


def test_settings_request_rejects_huge_expansion():
    with pytest.raises(ValidationError):
        ProcessSettingsRequest(mask_expansion=500)


def test_settings_request_accepts_negative_erode():
    s = ProcessSettingsRequest(mask_expansion=-5)
    assert s.mask_expansion == -5


def test_settings_request_rejects_invalid_feather():
    with pytest.raises(ValidationError):
        ProcessSettingsRequest(mask_feathering=99)


def test_settings_request_rejects_long_resolution():
    with pytest.raises(ValidationError):
        ProcessSettingsRequest(output_resolution="x" * 64)


# ---------------------------------------------------------------------------
# JobEvent payload (PROCESS-003 SSE)
# ---------------------------------------------------------------------------


def test_job_event_serialises_with_required_fields():
    ev = JobEvent(stage="inpaint", progress=42, frames_processed=10, total_frames=30)
    d = json.loads(ev.model_dump_json())
    assert d["stage"] == "inpaint"
    assert d["progress"] == 42
    assert d["warnings"] == []
    assert d["terminal"] is False


def test_job_event_terminal_sets_fields():
    ev = JobEvent(stage="completed", progress=100, terminal=True)
    assert ev.terminal is True


# ---------------------------------------------------------------------------
# Mask rebin (downsample) pure helper
# ---------------------------------------------------------------------------


def test_rebin_grid_noop_for_factor_le_one():
    from app.services.mask_render import rebin_grid

    g = [[0.0, 1.0], [1.0, 0.0]]
    assert rebin_grid(g, factor=1) is g


def test_rebin_grid_averages_blocks():
    from app.services.mask_render import rebin_grid

    grid = [
        [1.0, 1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 1.0],
        [0.0, 0.0, 1.0, 1.0],
    ]
    out = rebin_grid(grid, factor=2)
    assert out == [[1.0, 0.0], [0.0, 1.0]]
