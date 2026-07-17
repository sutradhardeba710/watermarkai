"""Stage 1 — heuristic pre-screen (SRS AI-001..004, PRD §13 Stage 1).

Pure CPU pass on a small frame sample. Uses numpy + OpenCV only (no ML weights):
  * Temporal persistence — a real logo is static across many frames.
  * Corner/edge-bias histogram — logos cluster in frame corners / top banner.
  * Alpha-like local statistics — watermark pixels are translucent overlays
    sitting above a varied background, so their variance across time is low
    while their mean sits near the global mean.

Outputs a ranked list of ROIs (bbox + persistence score) that Stage 2 (YOLO)
inspects in detail. Keeping Stage 1 deterministic + Apache-clean means the
project never depends on the AGPL YOLO weights for the *suggestion* path.

numpy / cv2 are imported inside the public functions so importing this module
on a 32-bit box (no numpy wheels) still succeeds and unit tests of the numeric
stage helpers can run against plain Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HeuristicROI:
    bbox: tuple[int, int, int, int]      # (x, y, w, h) in source pixels
    persistence: float                   # 0..1, higher = more static
    corner_bias: float                   # 0..1, higher = nearer a corner/banner
    transparency: float                   # 0..1, heuristic alpha likelihood
    score: float                         # weighted stage-1 score (0..1)


def _import_heavy():
    import numpy as np
    return np


def prescreen_frames(frames, frame_w: int, frame_h: int,
                     *, grid: int = 8, corner_weight: float = 0.25) -> list[HeuristicROI]:
    """Locate compact, persistent edge overlays near the frame boundary.

    Watermarks are small and temporally stable. A coarse fixed grid makes an
    entire static corner look like a watermark, so this pass instead groups
    stable edge pixels into tight connected components. The grid and
    corner_weight arguments remain accepted for API compatibility.
    """
    del grid, corner_weight
    np = _import_heavy()
    if not frames:
        return []
    import cv2

    gray_frames = []
    for frame in frames:
        arr = np.asarray(frame)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        if arr.ndim == 2:
            gray_frames.append(arr)
    if not gray_frames:
        return []

    stack = np.stack(gray_frames).astype(np.float32)
    median = np.median(stack, axis=0).astype(np.uint8)
    temporal_std = stack.std(axis=0)
    actual_h, actual_w = median.shape[:2]
    frame_w = actual_w or frame_w
    frame_h = actual_h or frame_h

    edges = cv2.Canny(median, 70, 160)
    stable_edges = ((temporal_std < 12.0) & (edges > 0)).astype(np.uint8) * 255

    border = np.zeros_like(stable_edges)
    border_h = max(1, int(frame_h * 0.22))
    border_w = max(1, int(frame_w * 0.18))
    border[:border_h, :] = 255
    border[frame_h - border_h:, :] = 255
    border[:, :border_w] = 255
    border[:, frame_w - border_w:] = 255

    components = cv2.bitwise_and(stable_edges, border)
    components = cv2.morphologyEx(
        components,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3)),
    )
    components = cv2.dilate(
        components,
        cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3)),
        iterations=1,
    )

    _count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(components)
    rois: list[HeuristicROI] = []
    for x, y, width, height, _area in stats[1:]:
        if (width < 8 or height < 4 or width > frame_w * 0.35
                or height > frame_h * 0.18):
            continue
        roi_edges = stable_edges[y:y + height, x:x + width]
        edge_density = float(np.count_nonzero(roi_edges) / max(1, width * height))
        raw_persistence = 1.0 - min(
            1.0,
            float(temporal_std[y:y + height, x:x + width].mean()) / 32.0,
        )
        if edge_density < 0.10 or raw_persistence < 0.35:
            continue

        x_margin = min(x, frame_w - (x + width))
        y_margin = min(y, frame_h - (y + height))
        edge_prior = 1.0 - min(
            1.0,
            0.5 * (
                x_margin / max(1.0, frame_w * 0.18)
                + y_margin / max(1.0, frame_h * 0.22)
            ),
        )
        if edge_prior < 0.60:
            continue
        edge_signal = min(1.0, edge_density / 0.12)
        persistence = min(1.0, 0.6 * raw_persistence + 0.4 * edge_signal)
        score = 0.45 * persistence + 0.35 * edge_signal + 0.20 * edge_prior

        padding = 4
        bx = max(0, int(x) - padding)
        by = max(0, int(y) - padding)
        bx2 = min(frame_w, int(x + width) + padding)
        by2 = min(frame_h, int(y + height) + padding)
        rois.append(HeuristicROI(
            bbox=(bx, by, bx2 - bx, by2 - by),
            persistence=round(persistence, 4),
            corner_bias=round(edge_prior, 4),
            transparency=round(edge_signal, 4),
            score=round(float(score), 4),
        ))
    rois.sort(key=lambda roi: roi.score, reverse=True)
    return rois


def top_rois(rois: list[HeuristicROI], *, k: int = 4, min_score: float = 0.2) -> list[HeuristicROI]:
    """Trim the Stage 1 list to the top-k ROIs above a minimum score. Returns at
    least one ROI when the input is non-empty so Stage 2 always has something to
    inspect (callers can mark everything low-confidence)."""
    if not rois:
        return []
    kept = [r for r in rois if r.score >= min_score]
    if not kept:
        kept = [rois[0]]
    return kept[:k]


def signals_from_roi(roi: HeuristicROI) -> dict:
    """Map a Stage 1 ROI to the ranker's signal inputs (PRD §13 Stage 5)."""
    return {
        "location_persistence": roi.persistence,
        "visual_repetition": roi.persistence,
        "transparency_probability": roi.transparency,
        "ocr_repetition": 0.0,
        "logo_probability": 0.0,
        "background_motion_probability": max(0.0, 1.0 - roi.persistence),
    }


__all__ = [
    "HeuristicROI",
    "prescreen_frames",
    "top_rois",
    "signals_from_roi",
]
