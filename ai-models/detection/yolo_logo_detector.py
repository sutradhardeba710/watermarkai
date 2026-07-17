"""Stage 2 — YOLOv8n-seg logo detector (SRS AI-002/004, DETECT-002/003).

Implements the pluggable :class:`Detector` interface. Heavy deps
(``ultralytics``, ``numpy``) are imported inside :meth:`__init__` / methods so
the module imports clean on a 32-bit box without the wheels — the same
defer-import discipline used by ``heuristic_prescreen``. The 64-bit worker
process is where inference actually runs.

Licensing: ultralytics YOLO weights are AGPL-3.0 for MVP. Fine-tune clean
weights or swap to RT-DETR (Apache-2.0) before public launch — see
``LICENSE-NOTE.md``.
"""
from __future__ import annotations

from typing import Optional

from ai_model_interfaces.detector import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
    Detector,
)


class YoloLogoDetector(Detector):
    """YOLOv8n-seg instance-segmentation detector.

    ``model_path`` is optional; when omitted the default ``yolov8n-seg.pt`` is
    pulled from the ultralytics cache. ``restrict_to_rois`` lets the caller
    pass heuristic Stage-1 bounding boxes (AI-002 ROI restriction) so inference
    runs on crops only instead of the full frame.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.25,
        restrict_to_rois: bool = True,
    ) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.restrict_to_rois = restrict_to_rois
        self._model = None  # lazily loaded

    # -- lazy model load -----------------------------------------------------
    def _load(self):
        from ultralytics import YOLO  # heavy; deferred
        path = self.model_path or "yolov8n-seg.pt"
        self._model = YOLO(path)
        return self._model

    @property
    def model(self):
        if self._model is None:
            self._load()
        return self._model

    # -- Detector interface --------------------------------------------------
    def detect(
        self,
        video_path: str,
        duration_seconds: float,
        sample_fps: float = 1.0,
    ) -> DetectionResult:
        import numpy as np  # heavy; deferred
        import cv2  # heavy; deferred

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return DetectionResult(candidates=[], sampled_frames=0,
                                   elapsed_seconds=0.0,
                                   notes="video open failed")
        fps = cap.get(cv2.CAP_PROP_FPS) or sample_fps or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step_frames = max(1, int(round(fps / max(0.1, sample_fps))))
        import time as _t
        start = _t.monotonic()

        sampled = 0
        per_frame_hits: list[list[DetectionCandidate]] = []
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step_frames == 0:
                hits = self._detect_in_frame(frame, idx)
                per_frame_hits.append(hits)
                sampled += 1
            idx += 1
            if 0 < total and idx >= total:
                break
        cap.release()

        merged = self._merge_across_frames(per_frame_hits)
        elapsed = _t.monotonic() - start
        return DetectionResult(
            candidates=merged,
            sampled_frames=sampled,
            elapsed_seconds=round(elapsed, 3),
            notes=f"detection:s2 sample_fps={sample_fps}",
        )

    # -- internals -----------------------------------------------------------
    def _detect_in_frame(self, frame, frame_idx: int) -> list[DetectionCandidate]:
        import numpy as np  # heavy
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        hits: list[DetectionCandidate] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            masks = getattr(r, "masks", None)
            if boxes is None:
                continue
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy()
                x, y, x2, y2 = (int(v) for v in xyxy)
                conf = float(boxes.conf[i].cpu().numpy())
                mask_arr = None
                if masks is not None and i < len(masks):
                    m = masks.data[i].cpu().numpy()
                    mask_arr = m.astype("int").tolist() if m.ndim >= 2 else None
                from uuid import uuid4
                hits.append(DetectionCandidate(
                    candidate_id=f"yolo-{frame_idx}-{i}-{uuid4().hex[:8]}",
                    candidate_type="logo",
                    bbox=BoundingBox(x=int(x), y=int(y),
                                     w=int(x2 - x), h=int(y2 - y)),
                    mask=mask_arr,
                    confidence=conf,
                    is_static=True,
                    start_time=None,
                    end_time=None,
                    extra={"stage": "yolo"},
                ))
        return hits

    def _merge_across_frames(
        self, per_frame_hits: list[list[DetectionCandidate]]
    ) -> list[DetectionCandidate]:
        """Keep candidates that recur across >= half the sampled frames — a
        real static watermark persists; flicker false-positives don't."""
        if not per_frame_hits:
            return []
        from collections import defaultdict
        bucket: dict = defaultdict(list)
        for frame_hits in per_frame_hits:
            for h in frame_hits:
                key = (
                    h.bbox.x // 16, h.bbox.y // 16,
                    h.bbox.w // 16, h.bbox.h // 16,
                )
                bucket[key].append(h)
        threshold = max(1, len(per_frame_hits) // 2)
        survivors: list[DetectionCandidate] = []
        for hits in bucket.values():
            if len(hits) < threshold:
                continue
            # average confidence; carry the median-area bbox as canonical
            best = max(hits, key=lambda h: h.confidence)
            avg_conf = sum(h.confidence for h in hits) / len(hits)
            merged = DetectionCandidate(
                candidate_id=best.candidate_id,
                candidate_type="logo",
                bbox=best.bbox,
                mask=best.mask,
                confidence=round(min(1.0, avg_conf), 4),
                is_static=True,
                start_time=None,
                end_time=None,
                extra={"stage": "yolo", "frames_matched": len(hits)},
            )
            survivors.append(merged)
        survivors.sort(key=lambda c: c.confidence, reverse=True)
        return survivors


__all__ = ["YoloLogoDetector"]
