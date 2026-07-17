"""Phase 6 pure-logic tests — preview arg builders, preview-window validators,
download-URL token shape, frame-count estimator.

No DB / Redis / numpy / cv2 / ffmpeg invocation — runs on the 32-bit box.
The ffmpeg arg lists are plain Python lists so their shape is asserted without
shelling out.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.preview import (
    ALLOWED_DURATIONS,
    DownloadUrlRequest,
    DownloadUrlResponse,
    PreviewRequest,
    PreviewResponse,
)


# ---------------------------------------------------------------------------
# Preview arg builders (SEC-007: arg lists only)
# ---------------------------------------------------------------------------


def _no_embedded_spaces(a: list[str]) -> bool:
    return all(" " not in str(tok) for tok in a)


def test_trim_clip_args_input_seek_and_duration():
    from app.services import preview as pv

    a = pv.trim_clip_args("in.mp4", "out.mp4", start_seconds=2.5, duration_seconds=5)
    assert a[0] == pv.get_settings().ffmpeg_bin
    assert "-ss" in a and "-t" in a
    # input seeking: -ss + -t precede -i
    ss_idx = a.index("-ss")
    t_idx = a.index("-t")
    i_idx = a.index("-i")
    assert ss_idx < t_idx < i_idx
    assert a[t_idx + 1] == "5"
    assert "-c" in a and a[a.index("-c") + 1] == "copy"
    assert _no_embedded_spaces(a)


def test_trim_clip_clamps_negative_start():
    from app.services import preview as pv

    a = pv.trim_clip_args("in.mp4", "out.mp4", start_seconds=-3.0, duration_seconds=3)
    assert a[a.index("-ss") + 1] == "0.000"


def test_proxy_target_args_has_scale_and_veryfast_preset():
    from app.services import preview as pv

    a = pv.proxy_target_args("in.mp4", "proxy.mp4", max_height=720)
    vf = a[a.index("-vf") + 1]
    assert vf == "scale=-2:720"
    assert a[a.index("-preset") + 1] == "veryfast"
    assert "-an" in a  # proxy is silent — audio is muxed later if needed


def test_extract_window_frames_args_delegates_to_encode_extractor():
    from app.services import preview as pv

    a = pv.extract_window_frames_args("w.mp4", "frames", fps=24.0)
    assert any(str(p).endswith("frame_%08d.png") for p in a)
    assert a[a.index("-vf") + 1] == "fps=24.0"


def test_encode_preview_args_no_audio_passthrough():
    from app.services import preview as pv

    a = pv.encode_preview_args("frames", "out.mp4", fps=25.0)
    assert "-an" in a
    assert a[a.index("-framerate") + 1] == "25.0"


# ---------------------------------------------------------------------------
# Frame-count estimator
# ---------------------------------------------------------------------------


def test_estimate_frame_count_uses_source_fps():
    from app.services import preview as pv

    assert pv.estimate_frame_count(5, 25.0) == 125
    assert pv.estimate_frame_count(3, 30.0) == 90
    assert pv.estimate_frame_count(10, 24.0) == 240


def test_estimate_frame_count_defaults_to_30_when_unknown():
    from app.services import preview as pv

    assert pv.estimate_frame_count(5, None) == 150
    assert pv.estimate_frame_count(5, 0) == 150


def test_estimate_frame_count_never_zero():
    from app.services import preview as pv

    assert pv.estimate_frame_count(0, 25.0) >= 1


# ---------------------------------------------------------------------------
# PreviewRequest validators (PREVIEW window)
# ---------------------------------------------------------------------------


def test_preview_request_defaults():
    b = PreviewRequest()
    assert b.duration_seconds == 5
    assert b.start_seconds is None


def test_preview_request_allowed_durations():
    assert ALLOWED_DURATIONS == {3, 5, 10}


@pytest.mark.parametrize("d", [3, 5, 10])
def test_preview_request_accepts_allowed_duration(d: int):
    PreviewRequest(duration_seconds=d)


@pytest.mark.parametrize("d", [0, 1, 4, 7, 11, 15, -2])
def test_preview_request_rejects_other_durations(d: int):
    with pytest.raises(ValidationError):
        PreviewRequest(duration_seconds=d)


def test_preview_request_rejects_negative_start():
    with pytest.raises(ValidationError):
        PreviewRequest(start_seconds=-1.0, duration_seconds=3)


def test_preview_request_rejects_absurd_start():
    with pytest.raises(ValidationError):
        PreviewRequest(start_seconds=10 ** 7, duration_seconds=3)


# ---------------------------------------------------------------------------
# DownloadUrlRequest/Response (DOWNLOAD-001..005)
# ---------------------------------------------------------------------------


def test_download_url_request_default_expiry():
    b = DownloadUrlRequest()
    assert b.expires_seconds == 1800


def test_download_url_request_rejects_below_min():
    with pytest.raises(ValidationError):
        DownloadUrlRequest(expires_seconds=10)


def test_download_url_request_rejects_above_cap():
    with pytest.raises(ValidationError):
        DownloadUrlRequest(expires_seconds=(24 * 3600) + 1)


def test_download_url_request_accepts_max():
    DownloadUrlRequest(expires_seconds=24 * 3600)


def test_download_url_response_schema_shape():
    exp = datetime.now(timezone.utc) + timedelta(seconds=300)
    r = DownloadUrlResponse(
        bucket="outputs", key="p/output.mp4", url="token:abc",
        expires_seconds=300, expires_at=exp,
    )
    assert r.bucket == "outputs"
    assert r.url.startswith("token:")


# ---------------------------------------------------------------------------
# PreviewResponse shape (PREVIEW-005)
# ---------------------------------------------------------------------------


def test_preview_response_minimal():
    r = PreviewResponse(
        project_id="p", status="ready", quality_mode="balanced",
        start_seconds=0.0, duration_seconds=5,
    )
    assert r.status == "ready"
    assert r.artifact_storage_key is None


def test_preview_response_failed_carries_error():
    r = PreviewResponse(
        project_id="p", status="failed", quality_mode="balanced",
        start_seconds=0.0, duration_seconds=5,
        error_code="PREVIEW_FAILED", error_message="boom",
    )
    assert r.error_code == "PREVIEW_FAILED"
