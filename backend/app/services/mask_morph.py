"""Server-side mask morphology (SRS MASK-004).

Pure-logic math so this runs and unit-tests on the 32-bit dev box (no numpy /
opencv). The painting is a naive per-pixel grid; Phase 5 replaces it with
`cv2`-based dilation/eroding on a real buffer for the inpaint mask, reusing
the *intent* (positive mask_expansion=dilate, negative=erode, feather=blur,
temporal_smoothing=intentionally no-op for a static mask).

The geometry painter here is reused by the geometry validator (rect, polygon
point-in-poly, brush discs) and by the resolve step that converts the stored
mask JSON into a binary grid for inpainting.
"""
from __future__ import annotations

from typing import Iterable


def empty_grid(w: int, h: int) -> list[list[int]]:
    return [[0 for _ in range(w)] for _ in range(h)]


def paint_rectangle(grid: list[list[int]], x: int, y: int, w: int, h: int, frame_w: int, frame_h: int) -> None:
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(frame_w, x + w), min(frame_h, y + h)
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            grid[yy][xx] = 1


def paint_disc(grid: list[list[int]], cx: float, cy: float, r: float, frame_w: int, frame_h: int) -> None:
    r2 = r * r
    x0 = max(0, int(cx - r))
    x1 = min(frame_w, int(cx + r) + 1)
    y0 = max(0, int(cy - r))
    y1 = min(frame_h, int(cy + r) + 1)
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
            if dx * dx + dy * dy <= r2:
                grid[yy][xx] = 1


def paint_polygon(grid: list[list[int]], points: list[tuple[float, float]], frame_w: int, frame_h: int) -> None:
    """Even-odd ray-cast fill. Points are screen coords."""
    if len(points) < 3:
        return
    for yy in range(frame_h):
        # build the x-crossings at scanline yy+0.5
        xs: list[float] = []
        n = len(points)
        for i in range(n):
            ax, ay = points[i]
            bx, by = points[(i + 1) % n]
            y0, y1 = (ay, by) if ay < by else (by, ay)
            yc = yy + 0.5
            if yc < y0 or yc >= y1:
                continue
            t = (yc - ay) / (by - ay) if (by - ay) != 0 else 0
            xcross = ax + t * (bx - ax)
            xs.append(xcross)
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            x0 = max(0, int(xs[k]))
            x1 = min(frame_w, int(xs[k + 1]) + 1)
            for xx in range(x0, x1):
                grid[yy][xx] = 1


def dilate(grid: list[list[int]], radius: int) -> list[list[int]]:
    """Square-kernel dilation. radius<=0 → copy."""
    if radius <= 0:
        return [row[:] for row in grid]
    h = len(grid)
    w = len(grid[0]) if h else 0
    out = empty_grid(w, h)
    for yy in range(h):
        for xx in range(w):
            if grid[yy][xx]:
                for dy in range(-radius, radius + 1):
                    yy2 = yy + dy
                    if 0 <= yy2 < h:
                        for dx in range(-radius, radius + 1):
                            xx2 = xx + dx
                            if 0 <= xx2 < w:
                                out[yy2][xx2] = 1
    return out


def erode(grid: list[list[int]], radius: int) -> list[list[int]]:
    """Square-kernel erosion. A pixel survives only if all neighbours within
    the kernel are set. radius<=0 → copy."""
    if radius <= 0:
        return [row[:] for row in grid]
    h = len(grid)
    w = len(grid[0]) if h else 0
    out = empty_grid(w, h)
    for yy in range(h):
        for xx in range(w):
            ok = True
            for dy in range(-radius, radius + 1):
                yy2 = yy + dy
                if not (0 <= yy2 < h):
                    ok = False
                    break
                row = grid[yy2]
                for dx in range(-radius, radius + 1):
                    xx2 = xx + dx
                    if not (0 <= xx2 < w) or not row[xx2]:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                out[yy][xx] = 1
    return out


def dilate_or_erode(grid: list[list[int]], mask_expansion: int) -> list[list[int]]:
    """Positive mask_expansion dilates; negative erodes (SRS MASK-004)."""
    if mask_expansion == 0:
        return [row[:] for row in grid]
    if mask_expansion > 0:
        return dilate(grid, mask_expansion)
    return erode(grid, -mask_expansion)


def feather(grid: list[list[int]], sigma: int) -> list[list[int]]:
    """Gaussian-ish blur of the binary mask into a 0..1 alpha grid.

    Returns a list[list[float]] in [0,1]. sigma<=0 returns a float copy of the
    binary grid (no blur). The kernel is a separable 1-tap Gaussian so this
    stays O(w·h·k) — fine for tiny validation grids, and Phase 5 swaps this for
    `cv2.GaussianBlur` on the real buffer.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if sigma <= 0:
        return [[float(v) for v in row] for row in grid]
    k = _kernel(sigma)
    half = len(k) // 2

    # horizontal pass — buffer of floats
    tmp = [[0.0] * w for _ in range(h)]
    for yy in range(h):
        row = grid[yy]
        for xx in range(w):
            acc = 0.0
            for t, wt in enumerate(k):
                xs = xx + t - half
                acc += wt * (row[xs] if 0 <= xs < w else 0)
            tmp[yy][xx] = acc
    # vertical pass
    out = [[0.0] * w for _ in range(h)]
    for yy in range(h):
        for xx in range(w):
            acc = 0.0
            for t, wt in enumerate(k):
                ys = yy + t - half
                acc += wt * (tmp[ys][xx] if 0 <= ys < h else 0)
            out[yy][xx] = acc
    return out


def _kernel(sigma: int) -> list[float]:
    """Build a small symmetric Gaussian-like kernel summing to 1."""
    import math

    k = max(sigma * 3, 1)
    xs = [i - k for i in range(2 * k + 1)]
    wts = [math.exp(-(x * x) / (2 * sigma * sigma)) for x in xs]
    s = sum(wts) or 1.0
    return [w / s for w in wts]


def _paint_tool(grid: list[list[int]], tool: str, geometry: dict, frame_w: int, frame_h: int) -> None:
    """Paint one shape (or a `multi` composite) into the binary grid."""
    if tool == "rectangle":
        paint_rectangle(
            grid,
            int(geometry.get("x", 0)),
            int(geometry.get("y", 0)),
            int(geometry.get("w", 0)),
            int(geometry.get("h", 0)),
            frame_w,
            frame_h,
        )
    elif tool == "polygon":
        pts = [(float(p[0]), float(p[1])) for p in geometry.get("points", [])]
        paint_polygon(grid, pts, frame_w, frame_h)
    elif tool == "brush":
        for s in geometry.get("strokes", []):
            paint_disc(grid, float(s.get("x", 0)), float(s.get("y", 0)), float(s.get("r", 1)), frame_w, frame_h)
    elif tool == "multi":
        # Composite mask: {"shapes": [{"tool": ..., "geometry": {...}}, ...]}
        for sub in geometry.get("shapes", []):
            _paint_tool(grid, sub.get("tool", ""), sub.get("geometry", {}) or {}, frame_w, frame_h)


def resolve_mask(
    tool: str,
    geometry: dict,
    frame_w: int,
    frame_h: int,
    mask_expansion: int = 0,
    mask_feathering: int = 0,
    temporal_smoothing: bool = False,
) -> list[list[float]]:
    """Convert a stored mask JSON into a morphology-applied alpha grid (SRS
    MASK-004). Phase 5 ingests the returned grid (or its cv2 equivalent) as the
    per-frame inpaint mask. temporal_smoothing is a static-mask no-op (MASK-005).
    """
    grid = empty_grid(frame_w, frame_h)
    _paint_tool(grid, tool, geometry, frame_w, frame_h)

    morph = dilate_or_erode(grid, mask_expansion)
    return feather(morph, mask_feathering)


__all__ = [
    "empty_grid",
    "paint_rectangle",
    "paint_disc",
    "paint_polygon",
    "dilate",
    "erode",
    "dilate_or_erode",
    "feather",
    "resolve_mask",
    "iter_grid",
]


def iter_grid(grid: Iterable[Iterable[int]]) -> Iterable[tuple[int, int, int]]:
    for yy, row in enumerate(grid):
        for xx, v in enumerate(row):
            yield yy, xx, v
