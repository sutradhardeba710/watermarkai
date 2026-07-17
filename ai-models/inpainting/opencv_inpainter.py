"""OpenCV inpainter (Phase 5 reconstruction path).

Quality modes (SRS RECON-004):
    fast     -> cv2.INPAINT_TELEA, radius 3
    balanced -> cv2.INPAINT_NS, radius 5  (default)
    high     -> cv2.INPAINT_NS, radius 7  + light temporal blend (filled in Phase 5)
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from ai_model_interfaces.detector import Inpainter


class OpenCVInpainter(Inpainter):
    def __init__(self) -> None:
        self._radius = {"fast": 3, "balanced": 5, "high": 7}
        self._flag = {"fast": cv2.INPAINT_TELEA, "balanced": cv2.INPAINT_NS, "high": cv2.INPAINT_NS}

    def inpaint_frame(
        self,
        frame_bgr: Any,
        mask_u8: Any,
        previous_frame: Any | None = None,
        quality: str = "balanced",
    ) -> Any:
        radius = self._radius.get(quality, 5)
        flag = self._flag.get(quality, cv2.INPAINT_NS)
        mask = (mask_u8 > 0).astype(np.uint8) * 255
        out = cv2.inpaint(frame_bgr, mask, radius, flag)
        if quality == "high" and previous_frame is not None:
            # minimal temporal stabilization (TEMP-001): blend a little of the
            # previous inpainted frame inside the masked region to cut flicker.
            blended = out.astype(np.float32)
            prev = previous_frame.astype(np.float32)
            alpha = (mask.astype(np.float32) / 255.0) * 0.15
            blended = blended * (1 - alpha[..., None]) + prev * alpha[..., None]
            out = blended.astype(np.uint8)
        return out
