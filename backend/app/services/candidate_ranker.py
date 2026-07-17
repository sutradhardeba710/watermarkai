"""Candidate ranker (SRS DETECT-005, DETECT-006; PRD §13 Stage 5).

Merges signals from the three detector stages into a single final score and
classifies High / Medium / Low confidence. Below the Low band → the candidate
is flagged `needs_manual_selection` (DETECT-006) and shown as a suggestion only,
never auto-saved as a mask.

The score is a weighted sum mirroring the PRD formula:

    Final Score =
        Location Persistence +
        Visual Repetition +
        Transparency Probability +
        OCR Repetition +
        Logo Probability -
        Background Motion Probability

Each input is pre-clamped to [0, 1] by the detector stages so the final score
lives in [-1, 5]; the thresholds below are tuned to that range.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


HIGH_THRESHOLD = 3.2
MEDIUM_THRESHOLD = 2.0
LOW_THRESHOLD = 1.0


@dataclass
class DetectorSignals:
    location_persistence: float = 0.0
    visual_repetition: float = 0.0
    transparency_probability: float = 0.0
    ocr_repetition: float = 0.0
    logo_probability: float = 0.0
    background_motion_probability: float = 0.0


@dataclass
class RankedCandidate:
    bbox: tuple[int, int, int, int]              # (x, y, w, h)
    confidence_label: str                        # high | medium | low | manual
    confidence_score: float
    needs_manual_selection: bool
    source: str = "merged"                       # heuristic | yolo | ocr | merged
    text: Optional[str] = None
    geometry: dict = field(default_factory=dict)
    detector_signals: DetectorSignals = field(default_factory=DetectorSignals)


def _clamp01(v: float) -> float:
    if v is None:
        return 0.0
    return max(0.0, min(1.0, float(v)))


def final_score(s: DetectorSignals) -> float:
    """PRD §13 Stage 5 formula. Inputs clamped to [0,1]; output in [-1, 5]."""
    lp = _clamp01(s.location_persistence)
    vr = _clamp01(s.visual_repetition)
    tp = _clamp01(s.transparency_probability)
    ocr = _clamp01(s.ocr_repetition)
    logo = _clamp01(s.logo_probability)
    bg = _clamp01(s.background_motion_probability)
    return lp + vr + tp + ocr + logo - bg


def confidence_label(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    if score >= LOW_THRESHOLD:
        return "low"
    return "manual"


def needs_manual(label: str) -> bool:
    return label in {"low", "manual"}


def rank(
    bbox: tuple[int, int, int, int],
    signals: DetectorSignals,
    *,
    source: str = "merged",
    text: Optional[str] = None,
    geometry: Optional[dict] = None,
) -> RankedCandidate:
    score = final_score(signals)
    label = confidence_label(score)
    return RankedCandidate(
        bbox=bbox,
        confidence_label=label,
        confidence_score=round(score, 4),
        needs_manual_selection=needs_manual(label),
        source=source,
        text=text,
        geometry=geometry or bbox_to_geometry(bbox),
        detector_signals=signals,
    )


def bbox_to_geometry(bbox: tuple[int, int, int, int]) -> dict:
    """Convert (x, y, w, h) → the rectangle geometry shape accepted by the masks
    schema (Phase 4). Reused by /approve to mint a WatermarkMask."""
    x, y, w, h = bbox
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h),
            "tool": "rectangle", "vertices": []}


def merge_dedup(
    candidates: list[RankedCandidate],
    *,
    iou_threshold: float = 0.3,
) -> list[RankedCandidate]:
    """Greedy non-max-suppression by IoU. Keeps the higher score per overlapping
    cluster. Toys (manual) are still surfaced when nothing else overlaps them so
    the user can choose to draw a mask manually."""
    if not candidates:
        return []
    sorted_cands = sorted(candidates, key=lambda c: c.confidence_score, reverse=True)
    kept: list[RankedCandidate] = []
    for c in sorted_cands:
        if any(_iou(c.bbox, k.bbox) >= iou_threshold for k in kept):
            continue
        kept.append(c)
    # Preserve a stable order: high → medium → low → manual, then by area desc.
    label_order = {"high": 0, "medium": 1, "low": 2, "manual": 3}
    kept.sort(key=lambda c: (label_order[c.confidence_label], -_area(c.bbox)))
    return kept


def _area(b: tuple[int, int, int, int]) -> int:
    return max(0, b[2]) * max(0, b[3])


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax1, ay1, ax2, ay2 = ax, ay, ax + aw, ay + ah
    bx1, by1, bx2, by2 = bx, by, bx + bw, by + bh
    inter_x0 = max(ax1, bx1)
    inter_y0 = max(ay1, by1)
    inter_x1 = min(ax2, bx2)
    inter_y1 = min(ay2, by2)
    iw = max(0, inter_x1 - inter_x0)
    ih = max(0, inter_y1 - inter_y0)
    inter = iw * ih
    union = _area(a) + _area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union


__all__ = [
    "DetectorSignals",
    "RankedCandidate",
    "final_score",
    "confidence_label",
    "needs_manual",
    "rank",
    "bbox_to_geometry",
    "merge_dedup",
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    "LOW_THRESHOLD",
]
