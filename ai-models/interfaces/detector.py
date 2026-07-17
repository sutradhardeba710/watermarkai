"""Pluggable AI model interfaces (SRS AI-001).

Implementations live in ai-models/detection, ai-models/tracking,
ai-models/inpainting, ai-models/segmentation. The pipeline imports these
abstract types so any concrete model can be swapped without rewriting the
task (AI-001 modular interface).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class DetectionCandidate:
    candidate_id: str
    candidate_type: str  # logo | text | timestamp | overlay
    bbox: BoundingBox
    mask: list[list[int]] | None  # binary mask HxW (downsampled acceptable)
    confidence: float
    is_static: bool
    start_time: float | None
    end_time: float | None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    candidates: list[DetectionCandidate]
    sampled_frames: int
    elapsed_seconds: float
    notes: str = ""


class Detector(ABC):
    """Auto watermark detection (DETECT-001..007)."""

    @abstractmethod
    def detect(self, video_path: str, duration_seconds: float, sample_fps: float = 1.0) -> DetectionResult:
        """Run detection over sampled frames; rank candidates per PRD §13 Stage 5."""


class Tracker(ABC):
    """Mask propagation across frames (SRS TRACK-001/002).

    MVP ships a static-only tracker; moving tracking is a later phase.
    """

    @abstractmethod
    def track(
        self, video_path: str, mask: list[list[int]], bbox: BoundingBox, start: float, end: float
    ) -> list[dict]:
        """Return per-frame masks/coords; each entry: {t, bbox, mask, confidence, lost}."""


class Inpainter(ABC):
    """Frame reconstruction (SRS RECON-001..008)."""

    @abstractmethod
    def inpaint_frame(
        self, frame_bgr: Any, mask_u8: Any, previous_frame: Any | None = None, quality: str = "balanced"
    ) -> Any:
        """Return an inpainted BGR frame of the same shape."""
