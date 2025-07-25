import reverse_geocoder as rg
import geopandas as gpd
from shapely.geometry import Point
import os

# Paths to GeoJSON files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'trmnl_data')
OCEAN_GEOJSON = os.path.join(DATA_DIR, 'ne_110m_ocean.geojson')
LAND_GEOJSON = os.path.join(DATA_DIR, 'ne_110m_land.geojson')
COUNTRY_GEOJSON = os.path.join(DATA_DIR, 'ne_110m_admin_0_countries.geojson')
MARINE_POLYS_GEOJSON = os.path.join(DATA_DIR, 'ne_110m_geography_marine_polys.geojson')

# Load GeoDataFrames (cache for performance)
_oceans_gdf = None
_land_gdf = None
_countries_gdf = None
_marine_gdf = None

def _load_oceans():
    global _oceans_gdf
    if _oceans_gdf is None:
        _oceans_gdf = gpd.read_file(OCEAN_GEOJSON)
    return _oceans_gdf

def _load_land():
    global _land_gdf
    if _land_gdf is None:
        _land_gdf = gpd.read_file(LAND_GEOJSON)
    return _land_gdf

def _load_countries():
    global _countries_gdf
    if _countries_gdf is None:
        _countries_gdf = gpd.read_file(COUNTRY_GEOJSON)
    return _countries_gdf

def _load_marine():
    global _marine_gdf
    if _marine_gdf is None:
        _marine_gdf = gpd.read_file(MARINE_POLYS_GEOJSON)
    return _marine_gdf

def get_country(lat, lon):
    """Return the country name for the given lat/lon, or None if not over a country."""
    countries = _load_countries()
    point = Point(lon, lat)
    match = countries[countries.contains(point)]
    if not match.empty:
        # Try several possible property names
        for prop in ('ADMIN', 'name', 'NAME', 'admin', 'country'):
            if prop in match.iloc[0]:
                return match.iloc[0][prop]
    return None

def get_continent(lat, lon):
    """Return the continent name for the given lat/lon, or None if not over land."""
    # Natural Earth land polygons have a 'CONTINENT' property
    land = _load_land()
    point = Point(lon, lat)
    match = land[land.contains(point)]
    if not match.empty:
        for prop in ('CONTINENT', 'continent', 'NAME', 'name'):
            if prop in match.iloc[0]:
                return match.iloc[0][prop]
    return None

def get_ocean(lat, lon):
    """Return the ocean/body of water name for the given lat/lon, or None if not over water."""
    marine = _load_marine()
    point = Point(lon, lat)
    match = marine[marine.contains(point)]
    if not match.empty:
        for prop in ('name', 'NAME', 'name_en'):
            if prop in match.iloc[0]:
                return match.iloc[0][prop]
    return None

def get_location_info(lat, lon):
    """
    Return a dict with the most specific location info for the given lat/lon:
    - country (if over a country)
    - continent (if over land but not a country)
    - ocean (if over water)
    """
    country = get_country(lat, lon)
    if country:
        return {'location_type': 'country', 'location_name': country}
    continent = get_continent(lat, lon)
    if continent:
        return {'location_type': 'continent', 'location_name': continent}
    ocean = get_ocean(lat, lon)
    if ocean:
        return {'location_type': 'ocean', 'location_name': ocean}
    return {'location_type': 'unknown', 'location_name': None} 