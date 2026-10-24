"""
Render the basemap image shown behind the rocket in the TRMNL plugin.

The map is drawn in Web Mercator at Leaflet zoom level 3 and centered on the
satellite. It is larger than any TRMNL screen so every layout can center it under
the rocket and crop the rest. TRMNL converts it to each device's bit depth.
"""

import json
import math
import os
import sys
from functools import lru_cache
from typing import Dict, List, Tuple

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as patheffects  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402
from PIL import Image  # noqa: E402

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "trmnl_data"
)
POSITION_FILE = os.path.join(DATA_DIR, "satgus_position.json")
LAND_GEOJSON = os.path.join(DATA_DIR, "ne_50m_land.geojson")
COUNTRY_GEOJSON = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.geojson")
MARINE_POLYS_GEOJSON = os.path.join(DATA_DIR, "ne_110m_geography_marine_polys.geojson")

# Image size in CSS pixels; templates display it at this size, centered on the rocket.
# Big enough that the rocket's off-center spots in each layout still cover the
# largest TRMNL-supported screens (1371x1028 CSS px, either orientation). 2048 is
# the whole world at zoom 3. Keep in sync with .satgus .map in
# trmnl_plugin/src/shared.liquid.
MAP_WIDTH = 2048
MAP_HEIGHT = 1792
# Rendered at 2x so high density screens (TRMNL X is 1.8x) stay sharp
PIXEL_RATIO = 2
ZOOM = 3

EARTH_RADIUS_M = 6378137.0
WORLD_WIDTH_M = 2 * math.pi * EARTH_RADIUS_M
METERS_PER_CSS_PX = WORLD_WIDTH_M / (256 * 2**ZOOM)
MAX_MERCATOR_LAT = 85.05112878

OCEAN_COLOR = "#c8c8c8"
LAND_COLOR = "#eeeeee"
BORDER_COLOR = "#8c8c8c"
COAST_COLOR = "#000000"
LABEL_COLOR = "#000000"
BORDER_WIDTH = 0.8
COAST_WIDTH = 1.2
LABEL_SIZE = 8
MAX_COUNTRY_LABELRANK = 4
MAX_MARINE_SCALERANK = 1
# Keep labels out from under the rocket (CSS px radius around the center)
ROCKET_CLEARANCE = 45


def lonlat_to_mercator(lat: float, lon: float) -> Tuple[float, float]:
    """Convert latitude/longitude in degrees to Web Mercator meters."""
    lat = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat))
    x = math.radians(lon) * EARTH_RADIUS_M
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS_M
    return x, y


@lru_cache(maxsize=1)
def _load_layers() -> Dict[str, gpd.GeoDataFrame]:
    """Load and project the map layers (cached)."""
    land = gpd.read_file(LAND_GEOJSON)
    countries = gpd.read_file(COUNTRY_GEOJSON)
    marine = gpd.read_file(MARINE_POLYS_GEOJSON)

    country_labels = countries[countries.LABELRANK <= MAX_COUNTRY_LABELRANK]
    country_labels = gpd.GeoDataFrame(
        {
            "text": country_labels.NAME.str.upper(),
            "rank": country_labels.LABELRANK,
            "italic": False,
        },
        geometry=gpd.points_from_xy(country_labels.LABEL_X, country_labels.LABEL_Y),
        crs=4326,
    )
    marine = marine[marine.scalerank <= MAX_MARINE_SCALERANK]
    marine_labels = gpd.GeoDataFrame(
        {"text": marine["name"].str.title(), "rank": marine.scalerank, "italic": True},
        geometry=marine.representative_point(),
        crs=4326,
    )
    # Oceans first, then countries by importance; earlier labels win collisions
    labels = gpd.GeoDataFrame(
        gpd.pd.concat([marine_labels, country_labels], ignore_index=True), crs=4326
    )

    def project(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        bounds = (-180, -MAX_MERCATOR_LAT, 180, MAX_MERCATOR_LAT)
        return gdf.clip_by_rect(*bounds).to_crs(3857)

    return {
        "land": project(land),
        "countries": project(countries),
        "labels": labels.to_crs(3857),
    }


def _world_offsets(center_x: float, half_width: float) -> List[float]:
    """X offsets needed to draw the world copies visible around the antimeridian."""
    offsets = [0.0]
    if center_x - half_width < -WORLD_WIDTH_M / 2:
        offsets.append(-WORLD_WIDTH_M)
    if center_x + half_width > WORLD_WIDTH_M / 2:
        offsets.append(WORLD_WIDTH_M)
    return offsets


def _place_labels(ax, labels: gpd.GeoDataFrame, offsets: List[float]) -> None:
    """Draw labels in priority order, skipping any that collide or cover the rocket."""
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    clearance = ROCKET_CLEARANCE * PIXEL_RATIO
    center_px = (fig.bbox.width / 2, fig.bbox.height / 2)
    halo = [patheffects.withStroke(linewidth=3, foreground="white")]
    placed: List[Bbox] = []

    for offset in offsets:
        for row in labels.itertuples():
            text: Text = ax.text(
                row.geometry.x + offset,
                row.geometry.y,
                row.text,
                ha="center",
                va="center",
                fontsize=LABEL_SIZE,
                color=LABEL_COLOR,
                fontweight="normal" if row.italic else "bold",
                style="italic" if row.italic else "normal",
                path_effects=halo,
            )
            box = text.get_window_extent(renderer).expanded(1.1, 1.2)
            near_rocket = (
                box.x0 - clearance < center_px[0] < box.x1 + clearance
                and box.y0 - clearance < center_px[1] < box.y1 + clearance
            )
            if (
                near_rocket
                or not fig.bbox.contains(box.x0, box.y0)
                or not fig.bbox.contains(box.x1, box.y1)
                or any(box.overlaps(other) for other in placed)
            ):
                text.remove()
                continue
            placed.append(box)


def render_map(latitude: float, longitude: float, file_path: str) -> None:
    """
    Render the basemap centered on the given position and save it as a PNG.

    Args:
        latitude: Center latitude in degrees
        longitude: Center longitude in degrees
        file_path: Where to write the PNG
    """
    layers = _load_layers()
    center_x, center_y = lonlat_to_mercator(latitude, longitude)
    half_w = MAP_WIDTH / 2 * METERS_PER_CSS_PX
    half_h = MAP_HEIGHT / 2 * METERS_PER_CSS_PX
    offsets = _world_offsets(center_x, half_w)

    dpi = 100 * PIXEL_RATIO
    fig = plt.figure(figsize=(MAP_WIDTH / 100, MAP_HEIGHT / 100), dpi=dpi)
    fig.patch.set_facecolor(OCEAN_COLOR)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor(OCEAN_COLOR)
    ax.set_xlim(center_x - half_w, center_x + half_w)
    ax.set_ylim(center_y - half_h, center_y + half_h)
    ax.axis("off")

    for offset in offsets:
        countries = layers["countries"].translate(xoff=offset)
        land = layers["land"].translate(xoff=offset)
        countries.plot(
            ax=ax, color=LAND_COLOR, edgecolor=BORDER_COLOR, linewidth=BORDER_WIDTH
        )
        land.boundary.plot(ax=ax, color=COAST_COLOR, linewidth=COAST_WIDTH)
    # plot() resets limits to the data; restore the view
    ax.set_xlim(center_x - half_w, center_x + half_w)
    ax.set_ylim(center_y - half_h, center_y + half_h)

    _place_labels(ax, layers["labels"], offsets)

    tmp_path = file_path + ".rgba.png"
    fig.savefig(tmp_path, dpi=dpi, facecolor=OCEAN_COLOR)
    plt.close(fig)
    with Image.open(tmp_path) as image:
        image.convert("L").save(file_path, optimize=True)
    os.remove(tmp_path)


def render_satgus_map(output_dir: str) -> str:
    """
    Render the map for the latest saved SATGUS position.

    Args:
        output_dir: Directory to write map.png into (created if missing)

    Returns:
        Path to the written PNG
    """
    with open(POSITION_FILE, "r") as f:
        position = json.load(f)
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "map.png")
    render_map(float(position["latitude"]), float(position["longitude"]), file_path)
    return file_path


if __name__ == "__main__":
    """Render map.png for the saved position into the given directory."""
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "_site"
    try:
        path = render_satgus_map(out_dir)
        print(f"Rendered map to {path}")
    except Exception as e:
        print(f"Error rendering map: {e}")
        exit(1)
