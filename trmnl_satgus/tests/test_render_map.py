"""
Tests for the basemap renderer.
"""

import pytest
from PIL import Image

from satgus.render_map import (
    MAP_HEIGHT,
    MAP_WIDTH,
    PIXEL_RATIO,
    WORLD_WIDTH_M,
    _world_offsets,
    lonlat_to_mercator,
    render_map,
)


def test_lonlat_to_mercator_origin():
    """Test that (0, 0) projects to the Mercator origin."""
    x, y = lonlat_to_mercator(0, 0)
    assert x == pytest.approx(0, abs=1e-6)
    assert y == pytest.approx(0, abs=1e-6)


def test_lonlat_to_mercator_clamps_poles():
    """Test that latitudes beyond the Mercator limit are clamped, not infinite."""
    _, y_pole = lonlat_to_mercator(90, 0)
    _, y_limit = lonlat_to_mercator(85.05112878, 0)
    assert y_pole == pytest.approx(y_limit)


def test_world_offsets_only_when_view_crosses_antimeridian():
    """Test that extra world copies are drawn only near the antimeridian."""
    half_width = WORLD_WIDTH_M / 8
    assert _world_offsets(0, half_width) == [0.0]
    assert _world_offsets(WORLD_WIDTH_M / 2 - 1, half_width) == [0.0, WORLD_WIDTH_M]
    assert _world_offsets(-WORLD_WIDTH_M / 2 + 1, half_width) == [0.0, -WORLD_WIDTH_M]


@pytest.mark.parametrize(
    "latitude,longitude",
    [(52, -65), (-15, 179.5), (81, 20)],
    ids=["canada", "antimeridian", "arctic"],
)
def test_render_map_writes_grayscale_png(tmp_path, latitude, longitude):
    """Test that the rendered map has the expected size and mode."""
    path = tmp_path / "map.png"
    render_map(latitude, longitude, str(path))

    with Image.open(path) as image:
        assert image.size == (MAP_WIDTH * PIXEL_RATIO, MAP_HEIGHT * PIXEL_RATIO)
        assert image.mode == "L"
        # Center is the satellite; make sure something was actually drawn
        assert image.getextrema() == (0, 255)
