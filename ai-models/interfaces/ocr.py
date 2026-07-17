"""Pluggable OCR provider interface (SRS AI-006/007, PRD §13 Stage 3).

The detection pipeline asks an ``OcrProvider`` to find text in cropped ROIs.
EasyOCR is the MVP primary; PaddleOCR is an optional secondary behind the same
interface so the choice is a config knob (AI-006), not a code change. Heavy
deps (easyocr / paddleocr) are NOT imported here — concrete providers defer
their import into ``__init__`` / method bodies so this file imports clean on a
machine without the wheels.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OcrHit:
    text: str
    bbox: tuple[int, int, int, int]   # (x, y, w, h) in the cropped ROIs frame
    confidence: float
    extra: dict = field(default_factory=dict)


class OcrProvider(ABC):
    """Text-watermark channel (SRS AI-006)."""

    @abstractmethod
    def read(self, frame_bgr, bbox: tuple[int, int, int, int]) -> list[OcrHit]:
        """OCR-read text inside the bbox of a BGR frame; return hits with text
        + per-hit confidence. Empty list means no readable text."""


__all__ = ["OcrHit", "OcrProvider"]
