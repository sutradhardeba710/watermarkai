"""Mask render bridge — turns the stored mask JSON into a `numpy.uint8` inpaint
mask for the worker (SRS RECON-001, MASK-004).

:func:`resolve_mask` (app.services.mask_morph) already produces a
`list[list[float]]` alpha grid with morphology applied. This module converts
that grid into a `numpy.uint8` (0/255) buffer suitable for `cv2.inpaint`, and
caches one mask per frame so a static mask is rendered once (SRS MASK-005).

The conversion is isolated behind an explicit `to_uint8` function so the rest
of the module import succeeds on the 32-bit dev box (numpy / cv2 are imported
lazily inside the functions that need them).
"""
from __future__ import annotations

from typing import Any

from app.core.errors import AppError
from app.services.mask_morph import resolve_mask as _resolve_mask_grid


def resolve_inpaint_mask(
    tool: str,
    geometry: dict,
    frame_w: int,
    frame_h: int,
    *,
    mask_expansion: int = 0,
    mask_feathering: int = 0,
    threshold: float = 0.05,
) -> object:
    """Build a `numpy.uint8` mask (.float thresholded to 0/255) for `cv2.inpaint`.

    The float grid from :func:`resolve_mask` is in [0,1]; pixels above the
    feather-edge threshold are treated as the inpaint region. numpy is imported
    here so the rest of the module is importable without it.
    """
    grid = _resolve_mask_grid(
        tool=tool,
        geometry=geometry,
        frame_w=frame_w,
        frame_h=frame_h,
        mask_expansion=mask_expansion,
        mask_feathering=mask_feathering,
    )
    return grid_to_uint8(grid, threshold)


def grid_to_uint8(grid: list[list[float]], threshold: float = 0.05) -> object:
    """Convert a `list[list[float]]` in [0,1] to a `numpy.uint8` (0/255) array.

    Lazily imports numpy. Raises :class:`AppError` if numpy is unavailable —
    callers in the worker propagate that as a job failure.
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - only on 32-bit CI
        raise AppError("DEPS_MISSING", "numpy is required to render the inpaint mask.", 503) from exc

    arr = np.array(grid, dtype=np.float32)
    mask = (arr >= threshold).astype(np.uint8) * 255
    return mask


def rebin_grid(grid: list[list[float]], factor: int = 8) -> list[list[float]]:
    """Downsample a float grid by an integer factor via naive block averaging.

    Pure helper (no numpy) used by unit tests and by the downscale path so a
    1920x1080 mask is not needlessly rebuilt for every frame when the inpaint
    runs on a proxy grid. Returns the input unchanged for factor<=1.
    """
    if factor <= 1 or not grid:
        return grid
    h = len(grid)
    w = len(grid[0]) if h else 0
    out_h = h // factor
    out_w = w // factor
    out: list[list[float]] = []
    for oy in range(out_h):
        row: list[float] = []
        for ox in range(out_w):
            acc = 0.0
            for dy in range(factor):
                base = grid[oy * factor + dy]
                for dx in range(factor):
                    acc += base[ox * factor + dx]
            row.append(acc / (factor * factor))
        out.append(row)
    return out


class StaticMaskCache:
    """Renders once, returns the same mask buffer for every subsequent frame.

    SRS MASK-005: a static mask is reused across all frames (TRACK-001). Moving
    tracking (TRACK-002) is out of MVP scope and not handled here.
    """
    def __init__(self, tool: str, geometry: dict, frame_w: int, frame_h: int,
                 mask_expansion: int = 0, mask_feathering: int = 0):
        self._args = (tool, geometry, frame_w, frame_h, mask_expansion, mask_feathering)
        self._mask: Any = None

    def get(self) -> object:
        if self._mask is None:
            self._mask = resolve_inpaint_mask(
                self._args[0], self._args[1], self._args[2], self._args[3],
                mask_expansion=self._args[4], mask_feathering=self._args[5],
            )
        return self._mask


__all__ = [
    "resolve_inpaint_mask",
    "grid_to_uint8",
    "rebin_grid",
    "StaticMaskCache",
]
