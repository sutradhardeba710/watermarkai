"""Static-only tracker (SRS TRACK-001).

MVP propagation strategy: a mask approved at any single frame is treated as
fixed across the whole clip — the killer assumption that makes Phase 5's
``StaticMaskCache`` valid. Moving-watermark tracking (TRACK-002) is a later
phase and deliberately a no-op here; callers get a constant per-frame mask back.
"""
from __future__ import annotations

from ai_model_interfaces.detector import BoundingBox, Tracker


class StaticTracker(Tracker):
    """Reuses one mask/bbox for every frame in [start, end] (TRACK-001)."""

    def track(
        self,
        video_path: str,
        mask: list,
        bbox: BoundingBox,
        start: float,
        end: float,
    ) -> list[dict]:
        # One entry per second of the window — enough for the inpaint cache to
        # key on a stable mask without re-running OCR/YOLO every frame.
        if end is None or start is None:
            return []
        if end <= start:
            return []
        step = 1.0
        entries: list[dict] = []
        t = start
        # guard against pathological inputs
        max_frames = 10_000
        i = 0
        while t <= end and i < max_frames:
            entries.append({
                "t": round(t, 6),
                "bbox": {"x": bbox.x, "y": bbox.y, "w": bbox.w, "h": bbox.h},
                "mask": mask,
                "confidence": 1.0,
                "lost": False,
            })
            t += step
            i += 1
        return entries


__all__ = ["StaticTracker"]
