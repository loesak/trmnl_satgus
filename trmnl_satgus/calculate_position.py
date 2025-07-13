"""
Satellite tracking module using skyfield library.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

from trmnl_satgus.fetch_tle import fetch_and_save_tle
from trmnl_satgus.location_utils import get_location_info


def calculate_initial_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the initial bearing (compass heading) from point 1 to point 2.
    Args:
        lat1, lon1: Latitude and longitude of the first point in degrees
        lat2, lon2: Latitude and longitude of the second point in degrees
    Returns:
        Initial bearing in degrees (0° = North, 90° = East)
    """
    import math
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.atan2(x, y)
    bearing_degrees = (math.degrees(bearing) + 360) % 360
    return bearing_degrees

class SatelliteTracker:
    """Track satellite positions and provide location data."""

    def __init__(self):
        """Initialize the satellite tracker."""
        self.ts = load.timescale()
        self.earth = wgs84

    def create_satellite_from_tle(
        self, name: str, line1: str, line2: str
    ) -> EarthSatellite:
        """
        Create a satellite object from TLE (Two-Line Element) data.

        Args:
            name: Satellite name
            line1: First line of TLE data
            line2: Second line of TLE data

        Returns:
            EarthSatellite object
        """
        return EarthSatellite(line1, line2, name, self.ts)

    def get_satellite_position(
        self, satellite: EarthSatellite, time: datetime | None = None
    ) -> Dict[str, float | str]:
        """
        Get satellite position at a specific time.

        Args:
            satellite: EarthSatellite object
            time: Time to get position for (defaults to current time)

        Returns:
            Dictionary with latitude, longitude, altitude, velocity, and timestamp
        """
        if time is None:
            time = datetime.now(timezone.utc)

        t = self.ts.from_datetime(time)
        geocentric = satellite.at(t)

        # Get subpoint (where satellite is directly overhead)
        subpoint = wgs84.subpoint_of(geocentric)

        # Calculate altitude directly from geocentric position
        earth_radius_km = 6378.137  # Earth's equatorial radius in km
        geocentric_distance_km = float(geocentric.distance().km)
        altitude_km = geocentric_distance_km - earth_radius_km

        # Get velocity
        velocity = geocentric.velocity.km_per_s
        velocity_km_s = float(np.linalg.norm(velocity))

        # Additional conversions
        altitude_miles = altitude_km * 0.621371
        velocity_kmh = velocity_km_s * 3600
        velocity_mph = velocity_kmh * 0.621371
        velocity_mps = velocity_km_s * 0.621371

        # Calculate heading (compass direction of ground track)
        # Use a small time delta (e.g., 1 second)
        from datetime import timedelta
        next_time = time + timedelta(seconds=1)
        t_next = self.ts.from_datetime(next_time)
        geocentric_next = satellite.at(t_next)
        subpoint_next = wgs84.subpoint_of(geocentric_next)
        heading_degrees = calculate_initial_bearing(
            float(subpoint.latitude.degrees),
            float(subpoint.longitude.degrees),
            float(subpoint_next.latitude.degrees),
            float(subpoint_next.longitude.degrees),
        )

        return {
            "latitude": float(subpoint.latitude.degrees),
            "longitude": float(subpoint.longitude.degrees),
            "altitude_km": altitude_km,
            "altitude_miles": altitude_miles,
            "velocity_km_s": velocity_km_s,
            "velocity_km_h": velocity_kmh,
            "velocity_mph": velocity_mph,
            "velocity_mps": velocity_mps,
            "heading_degrees": heading_degrees,
            "timestamp": time.isoformat(),
            # Add location info
            **get_location_info(float(subpoint.latitude.degrees), float(subpoint.longitude.degrees)),
        }

    def get_satellite_pass(
        self, satellite: EarthSatellite, observer_lat: float, observer_lon: float
    ) -> List[Dict[str, float | str]]:
        """
        Calculate satellite pass over an observer location.

        Args:
            satellite: EarthSatellite object
            observer_lat: Observer latitude in degrees
            observer_lon: Observer longitude in degrees

        Returns:
            List of position dictionaries during the pass
        """
        observer = self.earth.latlon(observer_lat, observer_lon)

        # Create time range (next 24 hours)
        now = datetime.now(timezone.utc)
        t0 = self.ts.from_datetime(now)
        t1 = self.ts.from_datetime(now.replace(hour=now.hour + 24))

        # Find when satellite is above horizon
        t, events = satellite.find_events(observer, t0, t1, altitude_degrees=0)

        positions = []
        for ti in t:
            position = self.get_satellite_position(satellite, ti.utc_datetime())
            positions.append(position)

        return positions

    def get_distance_to_satellite(
        self,
        satellite: EarthSatellite,
        observer_lat: float,
        observer_lon: float,
        time: datetime | None = None,
    ) -> float:
        """
        Calculate distance from observer to satellite.

        Args:
            satellite: EarthSatellite object
            observer_lat: Observer latitude in degrees
            observer_lon: Observer longitude in degrees
            time: Time to calculate distance for (defaults to current time)

        Returns:
            Distance in kilometers
        """
        if time is None:
            time = datetime.now(timezone.utc)

        t = self.ts.from_datetime(time)
        observer = self.earth.latlon(observer_lat, observer_lon)

        geocentric = satellite.at(t)
        difference = geocentric - observer.at(t)

        return float(difference.distance().km)


TLE_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "trmnl_data", "satgus_tle.json"
)


def load_tle() -> dict:
    """Load TLE data from the cached file."""
    if not os.path.exists(TLE_CACHE_FILE):
        # If TLE file doesn't exist, fetch and save it
        return fetch_and_save_tle()
    with open(TLE_CACHE_FILE, "r") as f:
        data = json.load(f)
    return data


def get_satgus_position() -> Dict[str, float | str]:
    """
    Get current SATGUS satellite position.

    Returns:
        Dictionary with SATGUS position data
    """
    tle = load_tle()
    tracker = SatelliteTracker()
    satgus = tracker.create_satellite_from_tle(tle["name"], tle["line1"], tle["line2"])
    return tracker.get_satellite_position(satgus)


def save_satellite_position(
    position: Dict[str, float | str], file_path: str = None
) -> None:
    """
    Save satellite position data to a JSON file.

    Args:
        position: Dictionary containing satellite position data
        file_path: Path to save the file (defaults to satgus_position.json)
    """
    if file_path is None:
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "trmnl_data",
            "satgus_position.json",
        )

    with open(file_path, "w") as f:
        json.dump(position, f, indent=2)


def fetch_and_save_satgus_position() -> Dict[str, float | str]:
    """
    Fetch current SATGUS satellite position and save it to file.

    Returns:
        Dictionary with SATGUS position data
    """
    position = get_satgus_position()
    save_satellite_position(position)
    return position


if __name__ == "__main__":
    """Main entry point for running the satellite position fetcher."""
    try:
        position = fetch_and_save_satgus_position()
        print("Successfully fetched SATGUS position:")
        print(f"  Latitude: {position['latitude']:.4f}°")
        print(f"  Longitude: {position['longitude']:.4f}°")
        print(f"  Altitude: {position['altitude_km']:.1f} km")
        print(f"  Altitude: {position['altitude_miles']:.1f} miles")
        print(f"  Velocity: {position['velocity_km_s']:.2f} km/s")
        print(f"  Velocity: {position['velocity_mps']:.2f} miles/s")
        print(f"  Velocity: {position['velocity_km_h']:.2f} km/h")
        print(f"  Velocity: {position['velocity_mph']:.2f} mph")
        print(f"  Heading: {position['heading_degrees']:.1f}° (compass)")
        print(f"  Timestamp: {position['timestamp']}")
        print(f"  Location: {position.get('location_type', 'unknown').capitalize()} - {position.get('location_name', 'N/A')}")
        print("Saved to satgus_position.json")
    except Exception as e:
        print(f"Error fetching satellite position: {e}")
        exit(1)
