"""Phase 4 pure-logic tests — mask geometry validation + morphology math.

Naive-array math, so this runs on 32-bit Python without numpy/opencv.
"""
from __future__ import annotations

import pytest

from app.schemas.masks import _validate_geometry
from app.services import mask_morph


# --- Geometry validation against frame dimensions ---


def test_validate_rectangle_ok():
    _validate_geometry("rectangle", {"x": 10, "y": 20, "w": 100, "h": 80}, 1280, 720)


def test_validate_rectangle_rejects_out_of_frame():
    with pytest.raises(ValueError):
        _validate_geometry("rectangle", {"x": 1000, "y": 600, "w": 500, "h": 200}, 1280, 720)


def test_validate_rectangle_rejects_zero_size():
    with pytest.raises(ValueError):
        _validate_geometry("rectangle", {"x": 0, "y": 0, "w": 0, "h": 10}, 1280, 720)


def test_validate_polygon_ok():
    _validate_geometry("polygon", {"points": [(0, 0), (100, 0), (100, 100), (0, 100)]}, 1280, 720)


def test_validate_polygon_rejects_too_few_points():
    with pytest.raises(ValueError):
        _validate_geometry("polygon", {"points": [(0, 0), (100, 0)]}, 1280, 720)


def test_validate_polygon_rejects_out_of_frame():
    with pytest.raises(ValueError):
        _validate_geometry("polygon", {"points": [(0, 0), (2000, 0), (0, 100)]}, 1280, 720)


def test_validate_brush_ok():
    _validate_geometry("brush", {"strokes": [{"x": 50, "y": 50, "r": 8}]}, 1280, 720)


def test_validate_brush_rejects_non_positive_radius():
    with pytest.raises(ValueError):
        _validate_geometry("brush", {"strokes": [{"x": 50, "y": 50, "r": 0}]}, 1280, 720)


def test_validate_unknown_tool_rejected():
    with pytest.raises(ValueError):
        _validate_geometry("lasso", {}, 1280, 720)


# --- Painting ---


def test_paint_rectangle_sets_pixels():
    g = mask_morph.empty_grid(20, 10)
    mask_morph.paint_rectangle(g, 5, 2, 4, 3, 20, 10)
    assert g[2][5] == 1 and g[4][8] == 1
    assert g[0][0] == 0 and g[9][19] == 0


def test_paint_disc_stays_in_radius():
    g = mask_morph.empty_grid(40, 40)
    mask_morph.paint_disc(g, 20, 20, 5, 40, 40)
    # corner far outside radius stays unset
    assert g[0][0] == 0
    # center definitely set
    assert g[20][20] == 1


def test_paint_polygon_fills_square():
    g = mask_morph.empty_grid(10, 10)
    mask_morph.paint_polygon(g, [(2, 2), (8, 2), (8, 8), (2, 8)], 10, 10)
    assert g[5][5] == 1
    assert g[0][0] == 0


# --- Morphology ---


def test_dilate_grows_mask():
    g = mask_morph.empty_grid(9, 9)
    g[4][4] = 1
    out = mask_morph.dilate(g, 1)
    # 3x3 cluster centred at (4,4)
    assert out[4][4] == 1 and out[3][4] == 1 and out[5][4] == 1 and out[4][3] == 1 and out[4][5] == 1
    # corners touched by the square kernel too
    assert out[3][3] == 1
    # far pixel stays clear
    assert out[0][0] == 0


def test_erode_eats_edges():
    g = mask_morph.empty_grid(9, 9)
    for yy in range(2, 7):
        for xx in range(2, 7):
            g[yy][xx] = 1
    out = mask_morph.erode(g, 1)
    # The 5x5 block erodes to a 3x3 block centred at (4,4)
    assert out[4][4] == 1
    assert out[2][2] == 0 and out[6][6] == 0
    assert out[3][3] == 1


def test_dilate_or_erode_zero_is_copy():
    g = mask_morph.empty_grid(5, 5)
    g[2][2] = 1
    out = mask_morph.dilate_or_erode(g, 0)
    assert out == g
    assert out is not g  # defensive copy


def test_dilate_or_erode_positive_dilates_negative_erodes():
    base = mask_morph.empty_grid(7, 7)
    base[3][3] = 1
    dil = mask_morph.dilate_or_erode(base, 1)  # +radius → dilate
    assert sum(sum(row) for row in dil) > 1
    block3 = [[1 if (2 <= x <= 4 and 2 <= y <= 4) else 0 for x in range(7)] for y in range(7)]
    ero = mask_morph.dilate_or_erode(block3, -1)  # -radius → erode
    assert sum(sum(row) for row in ero) < sum(sum(row) for row in block3)
    assert sum(sum(row) for row in ero) == 1  # 3x3 block erodes to its center pixel


def test_feather_blurs_into_floats_in_unit_range():
    g = mask_morph.empty_grid(21, 21)
    # a large lit region so the interior stays ~1 after blur with sigma=1
    for yy in range(5, 16):
        for xx in range(5, 16):
            g[yy][xx] = 1
    f = mask_morph.feather(g, 1)
    assert all(isinstance(v, float) for row in f for v in row)
    assert all(0.0 <= v <= 1.0001 for row in f for v in row)
    # interior stays ~1, far corner stays ~0
    assert f[10][10] > 0.9
    assert f[0][0] < 0.05


def test_feather_zero_returns_float_copy():
    g = mask_morph.empty_grid(4, 4)
    g[1][1] = 1
    f = mask_morph.feather(g, 0)
    assert f[1][1] == 1.0 and f[0][0] == 0.0
    assert all(isinstance(v, float) for row in f for v in row)


# --- resolve_mask end-to-end ---


def test_resolve_mask_rectangle_with_expansion_and_feather():
    out = mask_morph.resolve_mask(
        tool="rectangle",
        geometry={"x": 45, "y": 45, "w": 10, "h": 10},
        frame_w=100,
        frame_h=100,
        mask_expansion=2,
        mask_feathering=0,
    )
    # interior of the original rect stays painted
    assert out[50][50] == 1.0
    # shell just outside the original rect, inside the dilated block, now painted
    # (original x∈[45,55), dilation+r2 → x∈[43,57) — column 44 is the new shell)
    assert out[44][50] == 1.0
    # far outside stays empty
    assert out[0][0] == 0.0


def test_resolve_mask_unknown_tool_returns_empty():
    out = mask_morph.resolve_mask("nope", {}, 20, 20)
    assert all(v == 0.0 for row in out for v in row)
