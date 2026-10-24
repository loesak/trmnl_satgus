"""
Tests for the precomputed ground track.
"""

import json
from datetime import datetime, timezone

import pytest

from satgus.render_map import WORLD_SIZE
from satgus.track import build_track, write_static_data

START = datetime(2026, 10, 24, 5, 19, 37, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def track():
    """An hour of track from a fixed start."""
    return build_track(start=START, hours=1)


def test_build_track_shape(track):
    """Test the track's header and entry layout."""
    assert track["start"] == int(START.timestamp()) // 60 * 60
    assert track["step"] == 60
    assert track["count"] == len(track["track"]) == 60
    assert track["map_url"].startswith(
        "https://loesak.github.io/trmnl_satgus/world.png?v="
    )
    for x, y, heading, altitude, velocity, location in track["track"]:
        assert 0 <= x < WORLD_SIZE
        assert 0 <= y <= WORLD_SIZE
        assert 0 <= heading < 360
        # Low Earth orbit: roughly 400-700 km up at about 7.5 km/s
        assert 40000 < altitude < 70000
        assert 700 < velocity < 800
        assert -1 <= location < len(track["locations"])


def test_build_track_moves_each_minute(track):
    """Test that consecutive entries differ (the satellite moves ~450 km a minute)."""
    positions = [(entry[0], entry[1]) for entry in track["track"]]
    assert all(a != b for a, b in zip(positions, positions[1:]))


def test_build_track_fits_trmnl_payload_limit():
    """Test that a full day stays well under TRMNL's 100 KB data limit."""
    data = build_track(start=START)
    assert len(json.dumps(data, separators=(",", ":"))) < 75 * 1024


def test_write_static_data_replaces_only_static_data(tmp_path):
    """Test that static data is written as a YAML-safe single-quoted JSON string."""
    settings = tmp_path / "settings.yml"
    settings.write_text("---\nstrategy: static\nstatic_data: ''\nname: SAT GUS\n")
    data = {"locations": ["Cote d'Ivoire"], "track": [[1, 2, 3, 4, 5, 0]]}

    write_static_data(str(settings), data)

    lines = settings.read_text().splitlines()
    assert lines[1] == "strategy: static"
    assert lines[3] == "name: SAT GUS"
    static = lines[2].removeprefix("static_data: '").removesuffix("'")
    static = static.replace("''", "'")
    assert json.loads(static) == data


def test_write_static_data_requires_key(tmp_path):
    """Test that a settings file without static_data is rejected."""
    settings = tmp_path / "settings.yml"
    settings.write_text("---\nstrategy: static\n")
    with pytest.raises(ValueError):
        write_static_data(str(settings), {})
