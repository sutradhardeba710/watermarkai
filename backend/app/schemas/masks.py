"""Mask schemas (SRS MASK-001..007)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _validate_geometry(kind: str, geometry: dict[str, Any], w: int, h: int) -> None:
    """Raise ValueError if geometry coords are outside the frame or malformed.

    SRS: validate mask geometry against project frame dimensions.
    """
    def _clamp_point(px: Any, py: Any) -> None:
        if not (isinstance(px, (int, float)) and isinstance(py, (int, float))):
            raise ValueError("points must be numeric")
        if not (0 <= float(px) <= w and 0 <= float(py) <= h):
            raise ValueError(f"point ({px},{py}) outside {w}x{h} frame")

    if kind == "rectangle":
        x, y, ww, hh = geometry.get("x"), geometry.get("y"), geometry.get("w"), geometry.get("h")
        if not all(isinstance(v, (int, float)) for v in (x, y, ww, hh)):
            raise ValueError("rectangle must have numeric x,y,w,h")
        if ww <= 0 or hh <= 0:
            raise ValueError("rectangle w/h must be positive")
        _clamp_point(x, y)
        if x + ww > w or y + hh > h:
            raise ValueError("rectangle extends beyond frame")
    elif kind == "polygon":
        pts = geometry.get("points")
        if not isinstance(pts, list) or len(pts) < 3:
            raise ValueError("polygon needs >=3 points")
        for px, py in pts:
            _clamp_point(px, py)
    elif kind == "brush":
        # brush strokes: list of {x,y,r} discs
        strokes = geometry.get("strokes")
        if not isinstance(strokes, list):
            raise ValueError("brush requires strokes[]")
        for s in strokes:
            if not isinstance(s, dict):
                raise ValueError("stroke must be an object")
            cx, cy, r = s.get("x"), s.get("y"), s.get("r")
            if not all(isinstance(v, (int, float)) for v in (cx, cy, r)):
                raise ValueError("stroke needs numeric x,y,r")
            if r <= 0:
                raise ValueError("stroke radius must be positive")
            # a stroke may clip the frame; that's fine, the per-frame painter masks.
    elif kind == "multi":
        # composite of simple shapes: {"shapes": [{"tool": ..., "geometry": {...}}]}
        shapes = geometry.get("shapes")
        if not isinstance(shapes, list) or not shapes:
            raise ValueError("multi requires non-empty shapes[]")
        for shape in shapes:
            if not isinstance(shape, dict):
                raise ValueError("shape must be an object")
            sub_tool = shape.get("tool")
            if sub_tool == "multi":
                raise ValueError("multi shapes cannot nest")
            sub_geo = shape.get("geometry")
            if not isinstance(sub_geo, dict):
                raise ValueError("shape needs a geometry object")
            _validate_geometry(sub_tool, sub_geo, w, h)
    else:
        raise ValueError(f"unknown mask tool '{kind}'")


class MaskRequest(BaseModel):
    tool: str = Field(..., description="rectangle | polygon | brush | multi")
    geometry: dict[str, Any]
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    mask_expansion: int = Field(default=0, ge=-200, le=200)  # dilate/erode radius (MASK-004)
    mask_feathering: int = Field(default=4, ge=0, le=64)     # Gaussian sigma (MASK-004)
    temporal_smoothing: bool = False
    apply_to_entire: bool = True                             # MVP: entire-video static (MASK-005)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @field_validator("tool")
    @classmethod
    def _tool_ok(cls, v: str) -> str:
        if v not in {"rectangle", "polygon", "brush", "multi"}:
            raise ValueError("tool must be rectangle | polygon | brush | multi")
        return v

    def validate_geometry(self, frame_w: int, frame_h: int) -> None:
        """Clamp+validate the incoming geometry against the project frame."""
        _validate_geometry(self.tool, self.geometry, frame_w, frame_h)


class MaskResponse(BaseModel):
    id: str
    project_id: str
    tool: str
    geometry: dict[str, Any]
    width: int
    height: int
    mask_expansion: int
    mask_feathering: int
    temporal_smoothing: bool
    apply_to_entire: bool
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}
