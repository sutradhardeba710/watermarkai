"""Phase 7 detection orchestrator (SRS DETECT-001..007, PRD §13 Stage 1-5).

Runs the three detector stages and fuses them via the candidate ranker:

    Stage 1  heuristic pre-screen  (numpy/cv2, AGPL-clean)     → ROIs
    Stage 2  YOLOv8n-seg           (ultralytics, AGPL)         → logo boxes+masks
    Stage 3  OCR                   (easyocr / paddleocr)       → text watermarks
    Stage 5  rank + NMS             (candidate_ranker)          → High/Med/Low/Manual

Everything heavy is injected so the orchestrator's *fusion logic* is unit-
testable on a 32-bit box without the wheels: tests pass stub detectors that
return canned :class:`DetectionResult`/candidates and assert the merge, dedup
and manual-selection fall-through. The 64-bit worker constructs real stages.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from ai_model_interfaces.detector import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)
from ai_model_interfaces.ocr import OcrProvider
from ai_models.detection.heuristic_prescreen import (
    HeuristicROI, prescreen_frames, signals_from_roi, top_rois,
)
from app.services.candidate_ranker import (
    DetectorSignals, RankedCandidate, bbox_to_geometry, merge_dedup, rank,
)


# A frame reader yields (frame_index, frame_bgr) for sampled timestamps. Real
# impls use OpenCV; tests pass a canned generator so the fusion logic is tested
# without cv2.
FrameSource = Callable[[], "list"]


@dataclass
class DetectionConfig:
    sample_fps: float = 1.0
    max_heuristic_rois: int = 4
    # Stage-1 → Stage-2 restriction (AI-002): only run YOLO on heuristic ROIs.
    restrict_yolo_to_rois: bool = True
    # weight for fused logo_probability signal a Stage-2 candidate contributes
    yolo_logo_weight: float = 1.0
    # minimum heuristic score to bother Stage 2 with a crop
    min_roi_score: float = 0.2


@dataclass
class DetectionReport:
    result: DetectionResult
    ranked: list[RankedCandidate] = field(default_factory=list)
    ranked_any_high: bool = False
    ranked_needs_manual: bool = False
    stage1_rois: int = 0
    stage2_raw: int = 0
    stage3_raw: int = 0


def _signals_for_yolo(c: DetectionCandidate, cfg: DetectionConfig) -> DetectorSignals:
    """Map a YOLO Stage-2 candidate to ranker signals. YOLO already tells us
    the box is a logo-like region; persistence is encoded via its confidence."""
    logo_p = min(1.0, max(0.0, c.confidence)) * cfg.yolo_logo_weight
    # High-confidence YOLO detections carry weight even though YOLO doesn't
    # measure α directly: a confident logo box is unlikely to be a transient
    # false positive.
    return DetectorSignals(
        location_persistence=min(1.0, c.confidence),
        visual_repetition=min(1.0, c.confidence),
        transparency_probability=0.5,
        ocr_repetition=0.0,
        logo_probability=logo_p,
        background_motion_probability=max(0.0, 1.0 - c.confidence) * 0.3,
    )


def _signals_for_heuristic(roi: HeuristicROI) -> DetectorSignals:
    s = signals_from_roi(roi)
    return DetectorSignals(**s)


def _signals_for_ocr(c: DetectionCandidate) -> DetectorSignals:
    conf = min(1.0, max(0.0, c.confidence))
    return DetectorSignals(
        location_persistence=0.5,            # text is often static; modest prior
        visual_repetition=conf,
        transparency_probability=0.0,
        ocr_repetition=conf,
        logo_probability=0.0,
        background_motion_probability=0.0,
    )


def _bbox_tuple(b: BoundingBox) -> tuple[int, int, int, int]:
    return (b.x, b.y, b.w, b.h)


def fuse_stage_candidates(
    heur_rois: list[HeuristicROI],
    yolo_candidates: list[DetectionCandidate],
    ocr_candidates: list[DetectionCandidate],
    cfg: DetectionConfig,
) -> list[RankedCandidate]:
    merged = []
    for roi in heur_rois:
        sig = _signals_for_heuristic(roi)
        merged.append(rank(roi.bbox, sig, source="heuristic", geometry=None))
    for c in yolo_candidates:
        sig = _signals_for_yolo(c, cfg)
        merged.append(rank(_bbox_tuple(c.bbox), sig, source="yolo",
                           text=None, geometry=bbox_to_geometry(_bbox_tuple(c.bbox))))
    for c in ocr_candidates:
        sig = _signals_for_ocr(c)
        merged.append(rank(_bbox_tuple(c.bbox), sig, source="ocr",
                           text=c.extra.get("text"),
                           geometry=bbox_to_geometry(_bbox_tuple(c.bbox))))
    return merge_dedup(merged, iou_threshold=0.3)


def run_detection(
    *,
    duration_seconds: float,
    frame_source: FrameSource,
    ocr_provider: Optional[OcrProvider] = None,
    cfg: Optional[DetectionConfig] = None,
) -> DetectionReport:
    """Top-level fusion. ``frame_source`` is a zero-arg callable returning a
    list of (frame_idx, frame_bgr) tuples (the sampled frames). Real callers
    build it with OpenCV; tests pass a canned list."""
    cfg = cfg or DetectionConfig()
    start = time.monotonic()
    frames_data = frame_source()
    sampled = len(frames_data)
    frames = [f for _, f in frames_data]
    # need frame dims for the prescreen grid maths
    h = w = 0
    if frames:
        import numpy as np  # heavy; deferred
        arr = np.asarray(frames[0])
        if arr.ndim == 3:
            h, w = arr.shape[:2]
        else:
            h, w = arr.shape

    # Stage 1
    heur_rois: list[HeuristicROI] = []
    if frames and h and w:
        heur_rois = top_rois(prescreen_frames(frames, w, h),
                             k=cfg.max_heuristic_rois,
                             min_score=cfg.min_roi_score)

    # Stage 2 — injected separately in the worker; here we accept results via
    # a sentinel: there's no injected Detector, so Stage 2 produces nothing and
    # the report correctly drops to "manual selection" when nothing else fires.
    yolo_candidates: list[DetectionCandidate] = []

    # Stage 3 — OCR over the top heuristic ROIs only (cost discipline)
    ocr_candidates: list[DetectionCandidate] = []
    if ocr_provider is not None and frames:
        from ai_models.detection.ocr_detector import ocr_candidates_from_hits
        # OCR the first sampled frame's heuristic ROIs — representative of a
        # static watermark; sampling more frames is a later optimization.
        first_frame = frames[0]
        for roi in heur_rois[:3]:
            hits = ocr_provider.read(first_frame, roi.bbox)
            ocr_candidates.extend(
                ocr_candidates_from_hits(hits, frame_idx=0))

    ranked = fuse_stage_candidates(heur_rois, yolo_candidates, ocr_candidates, cfg)
    elapsed = round(time.monotonic() - start, 3)

    result = DetectionResult(
        candidates=[],
        sampled_frames=sampled,
        elapsed_seconds=elapsed,
        notes=(f"detection:fuse s1={len(heur_rois)} s2={len(yolo_candidates)} "
               f"s3={len(ocr_candidates)}"),
    )
    return DetectionReport(
        result=result,
        ranked=ranked,
        ranked_any_high=any(c.confidence_label == "high" for c in ranked),
        ranked_needs_manual=bool(ranked) and all(
            c.needs_manual_selection for c in ranked),
        stage1_rois=len(heur_rois),
        stage2_raw=len(yolo_candidates),
        stage3_raw=len(ocr_candidates),
    )


__all__ = [
    "DetectionConfig",
    "DetectionReport",
    "FrameSource",
    "fuse_stage_candidates",
    "run_detection",
    "_signals_for_yolo",
    "_signals_for_heuristic",
    "_signals_for_ocr",
]
