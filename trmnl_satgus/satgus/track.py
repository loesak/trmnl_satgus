"""
Precompute SATGUS's ground track for the TRMNL plugin.

TRMNL regenerates a Static-data plugin on every refresh, but re-renders a polling
plugin only when its data changes. So instead of publishing one position that goes
stale whenever GitHub Actions skips a scheduled run, we publish a day of positions
(one per minute) as the plugin's static data, and the template picks the entry for
its render time (trmnl.system.timestamp_utc).

Each track entry is compact integers, formatted by the template:
[world x px, world y px, heading deg, altitude km x100, velocity km/s x100, location]
where location indexes the "locations" list (-1 when unknown).
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import numpy as np
from skyfield.api import wgs84

from satgus.calculate_position import SatelliteTracker, load_tle
from satgus.location_utils import get_location_info
from satgus.render_map import map_version, world_px

STEP_SECONDS = 60
# GitHub has gone ~10h between scheduled runs; a day keeps the screen current
DURATION_HOURS = 24
EARTH_RADIUS_KM = 6378.137
WORLD_MAP_URL = "https://loesak.github.io/trmnl_satgus/world.png"


def _bearings(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Initial compass bearing (0 = north) from each point 1 to each point 2."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_lambda = np.radians(lon2 - lon1)
    x = np.sin(delta_lambda) * np.cos(phi2)
    y = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(delta_lambda)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def build_track(
    start: datetime | None = None,
    hours: int = DURATION_HOURS,
    step_seconds: int = STEP_SECONDS,
) -> Dict[str, Any]:
    """
    Compute the ground track from start (default: the current minute).

    Args:
        start: First entry's time (UTC); truncated to the step
        hours: How far ahead to compute
        step_seconds: Seconds between entries

    Returns:
        Static data for the plugin (see module docstring)
    """
    if start is None:
        start = datetime.now(timezone.utc)
    start_epoch = int(start.timestamp()) // step_seconds * step_seconds
    count = hours * 3600 // step_seconds

    tle = load_tle()
    tracker = SatelliteTracker()
    satellite = tracker.create_satellite_from_tle(
        tle["name"], tle["line1"], tle["line2"]
    )

    times = [
        datetime.fromtimestamp(start_epoch + i * step_seconds, tz=timezone.utc)
        for i in range(count)
    ]
    t = tracker.ts.from_datetimes(times)
    t_next = tracker.ts.from_datetimes([time + timedelta(seconds=1) for time in times])

    geocentric = satellite.at(t)
    subpoint = wgs84.subpoint_of(geocentric)
    subpoint_next = wgs84.subpoint_of(satellite.at(t_next))
    lats = subpoint.latitude.degrees
    lons = subpoint.longitude.degrees
    altitudes = geocentric.distance().km - EARTH_RADIUS_KM
    velocities = np.linalg.norm(geocentric.velocity.km_per_s, axis=0)
    headings = _bearings(
        lats, lons, subpoint_next.latitude.degrees, subpoint_next.longitude.degrees
    )

    locations: List[str] = []
    track: List[List[int]] = []
    for lat, lon, heading, altitude, velocity in zip(
        lats, lons, headings, altitudes, velocities
    ):
        name = get_location_info(float(lat), float(lon))["location_name"]
        if name is None:
            location = -1
        else:
            if name not in locations:
                locations.append(name)
            location = locations.index(name)
        x, y = world_px(float(lat), float(lon))
        track.append(
            [
                x,
                y,
                round(float(heading)) % 360,
                round(float(altitude) * 100),
                round(float(velocity) * 100),
                location,
            ]
        )

    return {
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
        "start": start_epoch,
        "step": step_seconds,
        "count": count,
        "map_url": f"{WORLD_MAP_URL}?v={map_version()}",
        "locations": locations,
        "track": track,
    }


def write_static_data(settings_path: str, data: Dict[str, Any]) -> None:
    """
    Store data as static_data in a trmnlp settings.yml, leaving the rest untouched.

    Args:
        settings_path: Path to trmnl_plugin/src/settings.yml
        data: Static data for the plugin
    """
    with open(settings_path, "r") as f:
        settings = f.read()
    # A single-quoted YAML scalar only needs embedded quotes doubled
    payload = json.dumps(data, separators=(",", ":")).replace("'", "''")
    updated, replaced = re.subn(
        r"^static_data:.*$",
        lambda _: f"static_data: '{payload}'",
        settings,
        count=1,
        flags=re.M,
    )
    if not replaced:
        raise ValueError(f"no static_data key in {settings_path}")
    with open(settings_path, "w") as f:
        f.write(updated)


if __name__ == "__main__":
    """Build the track and write it into the given settings.yml (or print it)."""
    try:
        data = build_track()
        if len(sys.argv) > 1:
            write_static_data(sys.argv[1], data)
            size = len(json.dumps(data, separators=(",", ":")))
            print(
                f"Wrote {data['count']} track entries ({size} bytes) to {sys.argv[1]}"
            )
        else:
            print(json.dumps(data, separators=(",", ":")))
    except Exception as e:
        print(f"Error building track: {e}")
        exit(1)
