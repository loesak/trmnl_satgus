"""
Render the world map shown behind the rocket in the TRMNL plugin.

The whole world is drawn once in Web Mercator at Leaflet zoom level 3 (2048x2048
CSS px). The plugin shifts it so the satellite's position (see world_px) sits
under the rocket, so the map only changes when its style or data does. TRMNL
converts it to each device's bit depth.
"""

import hashlib
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
LAND_GEOJSON = os.path.join(DATA_DIR, "ne_50m_land.geojson")
COUNTRY_GEOJSON = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.geojson")
MARINE_POLYS_GEOJSON = os.path.join(DATA_DIR, "ne_110m_geography_marine_polys.geojson")

# Inputs that change how the map looks; their hash versions the published image
MAP_INPUTS = [__file__, LAND_GEOJSON, COUNTRY_GEOJSON, MARINE_POLYS_GEOJSON]
# Rendered at 2x so high density screens (TRMNL X is 1.8x) stay sharp
PIXEL_RATIO = 2
ZOOM = 3

EARTH_RADIUS_M = 6378137.0
WORLD_WIDTH_M = 2 * math.pi * EARTH_RADIUS_M
# The world is square in Web Mercator: 2048x2048 CSS px at zoom 3. Keep in sync
# with .satgus .world in trmnl_plugin/src/shared.liquid.
WORLD_SIZE = 256 * 2**ZOOM
METERS_PER_CSS_PX = WORLD_WIDTH_M / WORLD_SIZE
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


def lonlat_to_mercator(lat: float, lon: float) -> Tuple[float, float]:
    """Convert latitude/longitude in degrees to Web Mercator meters."""
    lat = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, lat))
    x = math.radians(lon) * EARTH_RADIUS_M
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS_M
    return x, y


def world_px(lat: float, lon: float) -> Tuple[int, int]:
    """Position of latitude/longitude on the world map, in CSS px from top-left."""
    x, y = lonlat_to_mercator(lat, lon)
    return (
        round((x + WORLD_WIDTH_M / 2) / METERS_PER_CSS_PX) % WORLD_SIZE,
        round((WORLD_WIDTH_M / 2 - y) / METERS_PER_CSS_PX),
    )


def map_version() -> str:
    """Short hash of everything that affects the map, to bust caches when it changes."""
    digest = hashlib.sha256()
    for path in MAP_INPUTS:
        with open(path, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:12]


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


def _place_labels(ax, labels: gpd.GeoDataFrame) -> None:
    """Draw labels in priority order, skipping any that collide or leave the map."""
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    halo = [patheffects.withStroke(linewidth=3, foreground="white")]
    placed: List[Bbox] = []

    for row in labels.itertuples():
        text: Text = ax.text(
            row.geometry.x,
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
        if (
            not fig.bbox.contains(box.x0, box.y0)
            or not fig.bbox.contains(box.x1, box.y1)
            or any(box.overlaps(other) for other in placed)
        ):
            text.remove()
            continue
        placed.append(box)


def render_world_map(file_path: str) -> None:
    """
    Render the whole world map and save it as a grayscale PNG.

    Args:
        file_path: Where to write the PNG
    """
    layers = _load_layers()
    half = WORLD_WIDTH_M / 2

    dpi = 100 * PIXEL_RATIO
    fig = plt.figure(figsize=(WORLD_SIZE / 100, WORLD_SIZE / 100), dpi=dpi)
    fig.patch.set_facecolor(OCEAN_COLOR)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor(OCEAN_COLOR)
    ax.axis("off")

    layers["countries"].plot(
        ax=ax, color=LAND_COLOR, edgecolor=BORDER_COLOR, linewidth=BORDER_WIDTH
    )
    layers["land"].boundary.plot(ax=ax, color=COAST_COLOR, linewidth=COAST_WIDTH)
    # plot() fits limits to the data; pin the view to the exact world square
    ax.set_xlim(-half, half)
    ax.set_ylim(-half, half)

    _place_labels(ax, layers["labels"])

    tmp_path = file_path + ".rgba.png"
    fig.savefig(tmp_path, dpi=dpi, facecolor=OCEAN_COLOR)
    plt.close(fig)
    with Image.open(tmp_path) as image:
        image.convert("L").save(file_path, optimize=True)
    os.remove(tmp_path)


if __name__ == "__main__":
    """Render world.png and version.txt (the map's hash) into the given directory."""
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "_site"
    try:
        os.makedirs(out_dir, exist_ok=True)
        render_world_map(os.path.join(out_dir, "world.png"))
        with open(os.path.join(out_dir, "version.txt"), "w") as f:
            f.write(map_version() + "\n")
        print(f"Rendered world map {map_version()} to {out_dir}")
    except Exception as e:
        print(f"Error rendering map: {e}")
        exit(1)
