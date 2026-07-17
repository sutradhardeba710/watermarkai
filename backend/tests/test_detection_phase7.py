"""Phase 7 pure-logic tests — frame sampling, candidate ranker, heuristic
prescreen import-ability + empty guards, OCR provider interface shape.

No numpy / cv2 / ultralytics / easyocr — runs on the 32-bit dev box. The heavy
numeric stage (`prescreen_frames`) is covered by imports + guards only; its
real numeric behaviour is verified on a 64-bit box with numpy.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

# Register the hyphenated `ai-models/` folders under Python-legal aliases so
# the tests can `import ai_models.detection.heuristic_prescreen`. The worker
# path-shim (`workers/ai_models_paths.py`) registers the same aliases in prod.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_AI_MODELS = _REPO_ROOT / "ai-models"


def _ensure_alias(alias: str, path: Path) -> None:
    if alias in sys.modules:
        return
    init = path / "__init__.py"
    if not init.exists():
        return  # do NOT create dirs/files from a test helper
    spec = importlib.util.spec_from_file_location(
        alias, init, submodule_search_locations=[str(path)])
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)


_ensure_alias("ai_models", _AI_MODELS)
_ensure_alias("ai_models.detection", _AI_MODELS / "detection")
_ensure_alias("ai_models.tracking", _AI_MODELS / "tracking")
_ensure_alias("ai_models.inpainting", _AI_MODELS / "inpainting")
_ensure_alias("ai_model_interfaces", _AI_MODELS / "interfaces")
_ensure_alias("ai_models.interfaces", _AI_MODELS / "interfaces")

from app.services.frame_sample import (
    crop_roi,
    sample_timestamps,
    scene_bucket_index,
)
from app.services.candidate_ranker import (
    DetectorSignals,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MEDIUM_THRESHOLD,
    bbox_to_geometry,
    confidence_label,
    final_score,
    merge_dedup,
    needs_manual,
    rank,
)


# ---------------------------------------------------------------------------
# Frame sampling (SRS FRAME-001..004)
# ---------------------------------------------------------------------------

class TestSampleTimestamps:
    def test_zero_or_negative_duration_returns_empty(self):
        assert sample_timestamps(0.0) == []
        assert sample_timestamps(-5.0) == []

    def test_min_samples_enforced_short_clip(self):
        # 3s clip @ 1fps → only 3 fits, but min is 10 → backfill to 10
        ts = sample_timestamps(3.0, sample_fps=1.0, min_samples=10)
        assert len(ts) == 10
        assert all(0 < t <= 3.0 + 1e-6 for t in ts)

    def test_one_fps_walk_for_minute(self):
        ts = sample_timestamps(60.0, sample_fps=1.0)
        # ~60 fits, no min/backfill needed
        assert 10 <= len(ts) <= 60
        assert ts[0] > 0
        assert ts[-1] <= 60.0 + 1e-6
        # strictly increasing
        assert all(b > a for a, b in zip(ts, ts[1:]))

    def test_max_samples_cap(self):
        # 600s @ 1fps = 600 fits → capped at default max 200
        ts = sample_timestamps(600.0, sample_fps=1.0, max_samples=50)
        assert len(ts) <= 50

    def test_invalid_fps_falls_back_to_one(self):
        ts = sample_timestamps(30.0, sample_fps=0.0)
        assert len(ts) >= 10
        assert all(0 < t <= 30.0 + 1e-6 for t in ts)

    def test_single_sample_middle(self):
        ts = sample_timestamps(10.0, sample_fps=1.0, min_samples=1, max_samples=1)
        assert ts == [5.0]


class TestCropRoi:
    def test_basic_expand_clamped(self):
        # bbox at corner expands but clamps to frame
        out = crop_roi((0, 0, 20, 20), frame_w=100, frame_h=100, padding=8)
        assert out == (0, 0, 28, 28)

    def test_clamps_to_frame_bounds(self):
        out = crop_roi((95, 95, 10, 10), frame_w=100, frame_h=100, padding=8)
        # x1/y1 cannot exceed 100
        assert out == (87, 87, 100, 100)

    def test_no_negative_origin(self):
        out = crop_roi((3, 3, 5, 5), frame_w=100, frame_h=100, padding=8)
        assert out[0] == 0
        assert out[1] == 0


class TestSceneBucket:
    def test_no_scenes_returns_zero(self):
        assert scene_bucket_index(5.0, []) == 0

    def test_first_bucket(self):
        assert scene_bucket_index(2.0, [5.0, 10.0]) == 0

    def test_middle_bucket(self):
        assert scene_bucket_index(7.0, [5.0, 10.0]) == 1

    def test_last_bucket_open_ended(self):
        # two boundaries → three buckets (0,1,2); 99s lands in the open-ended tail
        assert scene_bucket_index(99.0, [5.0, 10.0]) == 2

    def test_boundary_belongs_to_next_scene(self):
        # timestamp exactly at a scene start belongs to the scene that starts there
        assert scene_bucket_index(5.0, [5.0, 10.0]) == 1


# ---------------------------------------------------------------------------
# Candidate ranker (SRS DETECT-005/006, PRD §13 Stage 5)
# ---------------------------------------------------------------------------

class TestFinalScore:
    def test_all_zero_signals_gives_negative_score(self):
        # 0 - 0 = 0 flat, but bg=0 too → 0.0 (within [−1,5])
        s = DetectorSignals()
        assert final_score(s) == 0.0

    def test_all_max_positive_signals(self):
        s = DetectorSignals(
            location_persistence=1.0,
            visual_repetition=1.0,
            transparency_probability=1.0,
            ocr_repetition=1.0,
            logo_probability=1.0,
            background_motion_probability=0.0,
        )
        assert final_score(s) == 5.0

    def test_full_background_motion_pushes_negative(self):
        s = DetectorSignals(background_motion_probability=1.0)
        assert final_score(s) == -1.0

    def test_inputs_clamped_above_one(self):
        s = DetectorSignals(location_persistence=2.5, logo_probability=10.0)
        assert final_score(s) == 2.0

    def test_inputs_clamped_below_zero(self):
        s = DetectorSignals(location_persistence=-3.0)
        assert final_score(s) == 0.0

    def test_none_inputs_treated_as_zero(self):
        s = DetectorSignals(location_persistence=None, logo_probability=None)  # type: ignore[arg-type]
        assert final_score(s) == 0.0


class TestConfidenceLabel:
    def test_high_band(self):
        assert confidence_label(HIGH_THRESHOLD) == "high"
        assert confidence_label(5.0) == "high"

    def test_medium_band(self):
        assert confidence_label(MEDIUM_THRESHOLD) == "medium"
        assert confidence_label(HIGH_THRESHOLD - 0.001) == "medium"

    def test_low_band(self):
        assert confidence_label(LOW_THRESHOLD) == "low"
        assert confidence_label(MEDIUM_THRESHOLD - 0.001) == "low"

    def test_manual_band_below_low(self):
        assert confidence_label(LOW_THRESHOLD - 0.001) == "manual"
        assert confidence_label(-1.0) == "manual"


def test_low_and_manual_candidates_require_manual_review():
    assert needs_manual("manual") is True
    assert needs_manual("low") is True
    for lbl in ("high", "medium"):
        assert needs_manual(lbl) is False


class TestRank:
    def test_rank_high_candidate(self):
        sig = DetectorSignals(
            location_persistence=1.0,
            visual_repetition=1.0,
            transparency_probability=1.0,
            ocr_repetition=0.5,
        )
        rc = rank((10, 10, 50, 50), sig, source="heuristic")
        assert rc.confidence_label == "high"
        assert rc.needs_manual_selection is False
        assert rc.source == "heuristic"
        assert rc.bbox == (10, 10, 50, 50)

    def test_rank_manual_candidate_when_background_dominates(self):
        sig = DetectorSignals(background_motion_probability=1.0)
        rc = rank((0, 0, 30, 30), sig)
        assert rc.confidence_label == "manual"
        assert rc.needs_manual_selection is True

    def test_geometry_shape_matches_masks_schema(self):
        rc = rank((5, 6, 50, 60), DetectorSignals())
        g = rc.geometry
        assert g["tool"] == "rectangle"
        assert g["x"] == 5.0 and g["y"] == 6.0
        assert g["w"] == 50.0 and g["h"] == 60.0
        assert g["vertices"] == []


def test_bbox_to_geometry_round_trip():
    g = bbox_to_geometry((1, 2, 3, 4))
    assert g == {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0,
                 "tool": "rectangle", "vertices": []}


class TestMergeDedupNMS:
    def test_empty_returns_empty(self):
        assert merge_dedup([]) == []

    def test_overlapping_keeps_higher_score(self):
        high = rank((10, 10, 50, 50), DetectorSignals(
            location_persistence=1.0, visual_repetition=1.0,
            transparency_probability=1.0, ocr_repetition=1.0))
        low = rank((11, 11, 50, 50), DetectorSignals())  # score 0 → manual
        merged = merge_dedup([low, high], iou_threshold=0.3)
        # high survives, low suppressed by IoU
        assert len(merged) == 1
        assert merged[0].confidence_score >= high.confidence_score

    def test_non_overlapping_both_kept(self):
        a = rank((0, 0, 20, 20), DetectorSignals(location_persistence=1.0))
        b = rank((500, 500, 20, 20), DetectorSignals(location_persistence=1.0))
        merged = merge_dedup([a, b], iou_threshold=0.3)
        assert len(merged) == 2

    def test_stable_label_ordering(self):
        high = rank((0, 0, 10, 10), DetectorSignals(
            location_persistence=1.0, visual_repetition=1.0,
            transparency_probability=1.0, ocr_repetition=1.0))
        manual = rank((300, 300, 10, 10), DetectorSignals(
            background_motion_probability=1.0))
        merged = merge_dedup([manual, high])
        assert merged[0].confidence_label == "high"
        assert merged[-1].confidence_label == "manual"


# ---------------------------------------------------------------------------
# Heuristic prescreen — import-ability + empty guards (32-bit safe)
# ---------------------------------------------------------------------------

def test_prescreen_imports_without_numpy():
    # Importing the module must not require numpy/cv2 (heavy imports deferred).
    mod = importlib.import_module("ai_models.detection.heuristic_prescreen")
    assert hasattr(mod, "prescreen_frames")
    assert hasattr(mod, "top_rois")
    assert hasattr(mod, "signals_from_roi")


def test_top_rois_empty_input():
    from ai_models.detection.heuristic_prescreen import top_rois
    assert top_rois([]) == []


def test_top_rois_returns_at_least_one_when_non_empty(monkeypatch):
    from ai_models.detection import heuristic_prescreen as hp
    # fabricate ROIs below min_score to confirm the floor-of-one behaviour
    fake = [hp.HeuristicROI(bbox=(0, 0, 1, 1), persistence=0.0,
                            corner_bias=0.0, transparency=0.0, score=0.05)]
    kept = hp.top_rois(fake, k=4, min_score=0.2)
    assert len(kept) == 1
    assert kept[0] is fake[0]


def test_prescreen_localizes_small_stable_border_overlay():
    import cv2
    import numpy as np
    from ai_models.detection.heuristic_prescreen import prescreen_frames

    frames = []
    for offset in range(6):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            "veo",
            (126, 112),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.rectangle(
            frame,
            (45 + offset, 45),
            (70 + offset, 75),
            (100, 100, 100),
            -1,
        )
        frames.append(frame)

    rois = prescreen_frames(frames, frame_w=160, frame_h=120)

    assert len(rois) == 1
    x, y, width, height = rois[0].bbox
    assert x >= 115 and y >= 95
    assert width < 45 and height < 30


def test_prescreen_blank_frames_return_no_false_candidates():
    import numpy as np
    from ai_models.detection.heuristic_prescreen import prescreen_frames

    frames = [np.zeros((120, 160, 3), dtype=np.uint8) for _ in range(4)]
    assert prescreen_frames(frames, frame_w=160, frame_h=120) == []

def test_signals_from_roi_maps_to_ranker_inputs():
    from ai_models.detection.heuristic_prescreen import signals_from_roi, HeuristicROI
    roi = HeuristicROI(bbox=(0, 0, 10, 10), persistence=0.6,
                       corner_bias=0.5, transparency=0.4, score=0.9)
    s = signals_from_roi(roi)
    assert s["location_persistence"] == 0.6
    assert s["visual_repetition"] == 0.6
    assert s["transparency_probability"] == 0.4
    assert s["ocr_repetition"] == 0.0
    assert s["logo_probability"] == 0.0
    assert s["background_motion_probability"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Detection orchestrator fusion (pure — no numpy/cv2; stages are injected)
# ---------------------------------------------------------------------------


def _bbox(x, y, w, h):
    from ai_models.interfaces import BoundingBox  # via ai_model_interfaces
    return BoundingBox(x=x, y=y, w=w, h=h)


class TestFuseStageCandidates:
    def cfg(self):
        from ai_models.detection.pipeline import DetectionConfig
        return DetectionConfig()

    def test_empty_inputs_empty_ranked(self):
        from ai_models.detection.pipeline import fuse_stage_candidates
        assert fuse_stage_candidates([], [], [], self.cfg()) == []

    def test_manual_fallthrough_when_everything_low(self):
        # No heuristic/YOLO/OCR → no candidates at all (DETECT-006 caller path)
        from ai_models.detection.pipeline import fuse_stage_candidates
        ranked = fuse_stage_candidates([], [], [], self.cfg())
        assert ranked == []

    def test_yolo_high_candidate_classified_high(self):
        from ai_models.detection.pipeline import (
            DetectionConfig, fuse_stage_candidates,
        )
        from ai_model_interfaces.detector import DetectionCandidate
        c = DetectionCandidate(
            candidate_id="y1", candidate_type="logo",
            bbox=_bbox(10, 10, 50, 50), mask=None, confidence=0.95,
            is_static=True, start_time=None, end_time=None, extra={"stage": "yolo"})
        ranked = fuse_stage_candidates([], [c], [], DetectionConfig())
        assert len(ranked) == 1
        assert ranked[0].source == "yolo"
        # confidence 0.95 → logo_probability=0.95, location_persistence 0.95,
        # visual_repetition 0.95, transparency 0.5, minus bg ~0.015 → ≈3.34 (high band)
        assert ranked[0].confidence_label == "high"

    def test_high_iou_dedup_keeps_higher_score(self):
        from ai_models.detection.pipeline import fuse_stage_candidates
        from ai_model_interfaces.detector import DetectionCandidate
        # two near-identical boxes; heuristic has tiny score → yolo wins, manual dropped
        from ai_models.detection.heuristic_prescreen import HeuristicROI
        roi = HeuristicROI(bbox=(10, 10, 50, 50), persistence=0.1,
                           corner_bias=0.0, transparency=0.0, score=0.1)
        yolo = DetectionCandidate(
            candidate_id="y1", candidate_type="logo",
            bbox=_bbox(11, 11, 50, 50), mask=None, confidence=0.9,
            is_static=True, start_time=None, end_time=None, extra={"stage": "yolo"})
        ranked = fuse_stage_candidates([roi], [yolo], [], self.cfg())
        # only the yolo one survives NMS (IoU > 0.3)
        assert len(ranked) == 1
        assert ranked[0].source == "yolo"

    def test_ocr_candidate_text_carried_through(self):
        from ai_models.detection.pipeline import fuse_stage_candidates
        from ai_model_interfaces.detector import DetectionCandidate
        ocr_c = DetectionCandidate(
            candidate_id="o1", candidate_type="text",
            bbox=_bbox(0, 0, 120, 30), mask=None, confidence=0.8,
            is_static=True, start_time=None, end_time=None,
            extra={"stage": "ocr", "text": "FOX"})
        ranked = fuse_stage_candidates([], [], [ocr_c], self.cfg())
        assert len(ranked) == 1
        assert ranked[0].source == "ocr"
        assert ranked[0].text == "FOX"
        # ocr_repetition=0.8 + location_persistence=0.5 + visual_repetition=0.8 → 2.1 (high)
        assert ranked[0].confidence_score >= 2.0


class TestRunWithNoStages:
    def test_no_frames_no_candidates(self):
        from ai_models.detection.pipeline import run_detection
        rep = run_detection(duration_seconds=0.0, frame_source=lambda: [])
        assert rep.ranked == []
        assert rep.ranked_any_high is False
        assert rep.result.sampled_frames == 0

    def test_fallthrough_marks_manual_when_no_high(self, monkeypatch):
        # A frame_source returning empty (no Stage2/3) → ranked empty → manual path
        from ai_models.detection.pipeline import run_detection
        rep = run_detection(duration_seconds=10.0, frame_source=lambda: [])
        assert rep.ranked_needs_manual is False  # nothing to even rank
        assert rep.ranked == []


class TestStaticTracker:
    def test_constant_mask_across_window(self):
        from ai_models.tracking.static_tracker import StaticTracker
        from ai_model_interfaces.detector import BoundingBox
        tr = StaticTracker()
        out = tr.track("x.mp4", [[1]], BoundingBox(0, 0, 10, 10), 0.0, 3.0)
        # entries at 0,1,2,3 — inclusive on both ends per the loop
        assert len(out) in (4,)
        assert all(e["mask"] == [[1]] for e in out)
        assert all(e["bbox"] == {"x": 0, "y": 0, "w": 10, "h": 10} for e in out)

    def test_empty_when_window_invalid(self):
        from ai_models.tracking.static_tracker import StaticTracker
        from ai_model_interfaces.detector import BoundingBox
        tr = StaticTracker()
        assert tr.track("x.mp4", [[1]], BoundingBox(0, 0, 10, 10), 1.0, 1.0) == []
        assert tr.track("x.mp4", [[1]], BoundingBox(0, 0, 10, 10), 2.0, 1.0) == []


class TestOcrInterface:
    def test_ocr_provider_is_abstract(self):
        from ai_model_interfaces.ocr import OcrProvider
        with pytest.raises(TypeError):
            OcrProvider()  # cannot instantiate ABC

    def test_ocr_provider_subclass_works(self):
        from ai_model_interfaces.ocr import OcrHit, OcrProvider
        class Fake(OcrProvider):
            def read(self, frame_bgr, bbox):
                return [OcrHit(text="hi", bbox=bbox, confidence=0.9)]
        hits = Fake().read(None, (0, 0, 10, 10))
        assert hits == [OcrHit(text="hi", bbox=(0, 0, 10, 10), confidence=0.9)]


# ---------------------------------------------------------------------------
# Phase 7 schemas — DETECT-007 / approval knobs
# ---------------------------------------------------------------------------

class TestApproveCandidateRequest:
    def test_defaults_acceptable(self):
        from app.schemas.candidates import ApproveCandidateRequest
        body = ApproveCandidateRequest()
        assert body.mask_expansion == 0
        assert body.mask_feathering == 4
        assert body.temporal_smoothing is False

    def test_rejects_expansion_out_of_band(self):
        from app.schemas.candidates import ApproveCandidateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ApproveCandidateRequest(mask_expansion=200)
        with pytest.raises(ValidationError):
            ApproveCandidateRequest(mask_expansion=-200)

    def test_rejects_feathering_out_of_band(self):
        from app.schemas.candidates import ApproveCandidateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ApproveCandidateRequest(mask_feathering=-1)
        with pytest.raises(ValidationError):
            ApproveCandidateRequest(mask_feathering=200)


class TestCandidateListResponse:
    def test_empty_list_sets_needs_manual(self):
        from app.schemas.candidates import CandidateListResponse
        r = CandidateListResponse(project_id="p1", candidates=[],
                                  needs_manual_selection=True,
                                  notes="manual please")
        assert r.candidates == []
        assert r.needs_manual_selection is True
        assert "manual" in (r.notes or "")

def test_detection_job_state_transitions_are_legal():
    from app.services.job_states import can_transition_values

    assert can_transition_values("processing_queued", "analyzing")
    assert can_transition_values("analyzing", "completed")

def test_candidate_creation_inherits_project_owner(monkeypatch):
    from app.repositories import candidates as candidate_repo

    captured = {}

    class CandidateStub:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class DbStub:
        def add(self, _row):
            pass

        def flush(self):
            pass

    monkeypatch.setattr(candidate_repo, "WatermarkCandidate", CandidateStub)
    candidate_repo.create_candidate(
        DbStub(),
        project_id="project-1",
        user_id="owner-1",
        candidate_type="logo",
        confidence=0.9,
        bounding_box={"x": 1, "y": 2, "w": 3, "h": 4},
    )

    assert captured["project_id"] == "project-1"
    assert "user_id" not in captured
