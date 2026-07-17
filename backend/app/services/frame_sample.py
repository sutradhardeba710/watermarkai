"""Frame sampling for auto-detection (SRS FRAME-001..004).

Pure math only — no FFmpeg, no OpenCV — so it runs + unit-tests on the 32-bit dev
box. The detector pulls actual frame pixels elsewhere; this module decides
*which timestamps* to sample.

Defaults (FRAME-001): one frame per second, minimum 10 samples, configurable
maximum. `sample_timestamps` returns a strictly-increasing list clamped to the
project's duration and the min/max window.

FRAME-003 (scene detection) splits the clip into scene buckets so a candidate
can be reported per-scene; the MVP detection task only consumes the first scene
boundary list to bound the search, but the math is shared here.
"""
from __future__ import annotations


def sample_timestamps(
    duration_seconds: float,
    sample_fps: float = 1.0,
    min_samples: int = 10,
    max_samples: int = 200,
) -> list[float]:
    """Return evenly-spaced timestamps (seconds) inside (0, duration].

    Behaviour:
      * duration <= 0      -> []
      * fewer fits than min -> raise the count to `min_samples` (still within
                               the duration, denser-than-1s sampling)
      * more fits than max -> cap at `max_samples` (sparse sampling)
      * step degenerates to <=0 when sample_fps <= 0 -> returns the min sample
                               count spaced across the duration. Defensive.
    """
    if duration_seconds is None or duration_seconds <= 0:
        return []
    if sample_fps <= 0:
        sample_fps = 1.0
    fits = int(duration_seconds * sample_fps)
    count = max(min_samples, min(max_samples, fits))
    # Spread the samples uniformly across the duration, anchored at t>0 so the
    # first frame isn't a black leader.
    if count <= 0:
        return []
    if count == 1:
        return [duration_seconds / 2]
    step = duration_seconds / count
    # t = step, 2*step, ..., count*step (== duration) — but clip trailing equal
    # values so we never return the exact last-second when the math rounds to it.
    ts = [round(step * (i + 1), 6) for i in range(count)]
    # drop any timestamp pinned beyond the duration (float safety)
    ts = [t for t in ts if 0 < t <= duration_seconds + 1e-6]
    if len(ts) < min_samples:
        # backfill with evenly-spaced midpoints so the minimum is met
        ts = list(_evenly_spaced(duration_seconds, min_samples))
    return ts


def _evenly_spaced(duration: float, count: int) -> list[float]:
    if count <= 1:
        return [duration / 2] if duration > 0 else []
    step = duration / (count + 1)
    return [round(step * (i + 1), 6) for i in range(count)]


def scene_bucket_index(
    timestamp: float,
    scene_starts: list[float],
) -> int:
    """Return the scene index containing `timestamp` given the scene boundary
    start times (ascending). Scene `i` spans ``[scene_starts[i], scene_starts[i+1])``;
    the last bucket is open-ended. The timestamp belongs to the first scene whose
    start is ``<=`` it, so the index is the count of starts not greater than the
    timestamp (with scene 0 covering everything before the first boundary)."""
    if not scene_starts:
        return 0
    idx = 0
    for start in scene_starts:
        if timestamp >= start:
            idx += 1
        else:
            break
    return idx


def crop_roi(bbox: tuple[int, int, int, int], frame_w: int, frame_h: int,
             padding: int = 8) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) clamped to the frame, expanded by `padding` px.
    Used to restrict YOLO inference to a high-score heuristic ROI (AI-002)."""
    x, y, w, h = bbox
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(frame_w, x + w + padding)
    y1 = min(frame_h, y + h + padding)
    return (x0, y0, x1, y1)


__all__ = ["sample_timestamps", "scene_bucket_index", "crop_roi"]
