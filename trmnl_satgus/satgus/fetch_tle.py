"""
TLE (Two-Line Element) data fetcher for satellite tracking.
"""

import json
import os
from datetime import datetime, timezone

import requests

TLE_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "trmnl_data", "satgus_tle.json"
)
TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=62713&FORMAT=TLE"


def fetch_latest_tle() -> dict:
    """
    Fetch the latest TLE for SATGUS from Celestrak.

    Returns:
        Dictionary containing TLE data with name, line1, line2, and fetched_at timestamp

    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If the TLE data is invalid
    """
    response = requests.get(TLE_URL, timeout=10)
    response.raise_for_status()
    lines = response.text.strip().splitlines()
    if len(lines) < 3:
        raise ValueError("Invalid TLE data fetched")
    return {
        "name": lines[0].strip(),
        "line1": lines[1].strip(),
        "line2": lines[2].strip(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def save_tle_to_file(tle: dict, file_path: str | None = None) -> None:
    """
    Save TLE data to a JSON file.

    Args:
        tle: Dictionary containing TLE data
        file_path: Path to save the file (defaults to TLE_CACHE_FILE)
    """
    if file_path is None:
        file_path = TLE_CACHE_FILE

    with open(file_path, "w") as f:
        json.dump(tle, f, indent=2)


def fetch_and_save_tle() -> dict:
    """
    Fetch the latest TLE data and save it to file.

    Returns:
        Dictionary containing the fetched TLE data
    """
    tle = fetch_latest_tle()
    save_tle_to_file(tle)
    return tle


if __name__ == "__main__":
    """Main entry point for running the TLE fetcher."""
    try:
        tle = fetch_and_save_tle()
        print(f"Successfully fetched TLE for {tle['name']}")
        print(f"Saved to {TLE_CACHE_FILE}")
    except Exception as e:
        print(f"Error fetching TLE: {e}")
        exit(1)
