"""
Tests for the world map renderer.
"""

import pytest
from PIL import Image

from satgus.render_map import (
    PIXEL_RATIO,
    WORLD_SIZE,
    lonlat_to_mercator,
    map_version,
    render_world_map,
    world_px,
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


def test_world_px_center_and_edges():
    """Test world pixel positions at the center, antimeridian and Mercator limits."""
    assert world_px(0, 0) == (WORLD_SIZE // 2, WORLD_SIZE // 2)
    # Both sides of the antimeridian land on the same (wrapped) column
    assert world_px(0, 180)[0] == world_px(0, -180)[0] == 0
    assert world_px(90, 0)[1] == 0
    assert world_px(-90, 0)[1] == WORLD_SIZE


def test_world_px_matches_known_city():
    """Test a known position (London) against its zoom 3 pixel coordinates."""
    assert world_px(51.507, -0.128) == (1023, 681)


def test_map_version_is_stable():
    """Test that the map version is a short, repeatable hash."""
    assert map_version() == map_version()
    assert len(map_version()) == 12


def test_render_world_map_writes_grayscale_png(tmp_path):
    """Test that the world map has the expected size and mode."""
    path = tmp_path / "world.png"
    render_world_map(str(path))

    with Image.open(path) as image:
        assert image.size == (WORLD_SIZE * PIXEL_RATIO, WORLD_SIZE * PIXEL_RATIO)
        assert image.mode == "L"
        # Black coastlines and white label halos were both drawn
        assert image.getextrema() == (0, 255)
