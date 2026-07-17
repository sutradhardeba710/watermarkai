"""Stage 3 — OCR text-watermark detector (SRS AI-006/007, PRD §13 Stage 3).

Reads text inside ROIs surfaced by Stages 1/2 and produces text-channel
candidates (``candidate_type='text'``). EasyOCR is the MVP primary provider;
PaddleOCR is the documented optional secondary behind :class:`OcrProvider`.
Heavy deps are imported inside provider constructors/methods, never at module
top, so this file imports on a 32-bit box without the wheels.
"""
from __future__ import annotations

from typing import Optional

from ai_model_interfaces.detector import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)
from ai_model_interfaces.ocr import OcrHit, OcrProvider


class EasyOcrProvider(OcrProvider):
    """EasyOCR-backed text reader (MVP primary, AI-006)."""

    def __init__(self, languages: Optional[list[str]] = None, gpu: bool = False) -> None:
        self.languages = languages or ["en"]
        self.gpu = gpu
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            import easyocr  # heavy; deferred
            self._reader = easyocr.Reader(self.languages, gpu=self.gpu)
        return self._reader

    def read(self, frame_bgr, bbox: tuple[int, int, int, int]) -> list[OcrHit]:
        import numpy as np  # heavy; deferred
        x, y, w, h = bbox
        h0, w0 = frame_bgr.shape[:2]
        x = max(0, x); y = max(0, y)
        x2 = min(w0, x + w); y2 = min(h0, y + h)
        crop = frame_bgr[y:y2, x:x2]
        if crop.size == 0:
            return []
        results = self.reader.readtext(crop)
        hits: list[OcrHit] = []
        for r in results:
            # easyocr returns (bbox_pts, text, conf) or (text, bbox, conf) by version
            if len(r) == 3:
                pts, text, conf = r
                hits.append(OcrHit(text=str(text), bbox=(x, y, x2 - x, y2 - y),
                                   confidence=float(conf)))
        return hits


class PaddleOcrProvider(OcrProvider):
    """Optional PaddleOCR provider (AI-006 alternate). Implemented to the same
    interface so the choice is config-only."""

    def __init__(self, use_gpu: bool = False, lang: str = "en") -> None:
        self.use_gpu = use_gpu
        self.lang = lang
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR  # heavy; deferred
            self._engine = PaddleOCR(use_angle_cls=True, lang=self.lang,
                                     use_gpu=self.use_gpu)
        return self._engine

    def read(self, frame_bgr, bbox: tuple[int, int, int, int]) -> list[OcrHit]:
        import numpy as np  # heavy; deferred
        x, y, w, h = bbox
        h0, w0 = frame_bgr.shape[:2]
        x = max(0, x); y = max(0, y)
        x2 = min(w0, x + w); y2 = min(h0, y + h)
        crop = frame_bgr[y:y2, x:x2]
        if crop.size == 0:
            return []
        res = self.engine.ocr(crop, cls=True)
        hits: list[OcrHit] = []
        if not res:
            return hits
        for line in res[0] or []:
            # paddleocr entry: [bbox_pts, (text, conf)]
            try:
                _pts, (text, conf) = line
                hits.append(OcrHit(text=str(text), bbox=(x, y, x2 - x, y2 - y),
                                   confidence=float(conf)))
            except (ValueError, TypeError):
                continue
        return hits


def ocr_candidates_from_hits(
    hits: list[OcrHit], frame_idx: int
) -> list[DetectionCandidate]:
    """Turn OCR hits on a frame into detection candidates."""
    from uuid import uuid4
    out: list[DetectionCandidate] = []
    for h in hits:
        x, y, w, hgt = h.bbox
        out.append(DetectionCandidate(
            candidate_id=f"ocr-{frame_idx}-{uuid4().hex[:8]}",
            candidate_type="text",
            bbox=BoundingBox(x=int(x), y=int(y), w=int(w), h=int(hgt)),
            mask=None,
            confidence=h.confidence,
            is_static=True,
            start_time=None,
            end_time=None,
            extra={"stage": "ocr", "text": h.text},
        ))
    return out


__all__ = [
    "EasyOcrProvider",
    "PaddleOcrProvider",
    "ocr_candidates_from_hits",
]
