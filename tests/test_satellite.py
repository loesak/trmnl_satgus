"""
Tests for the satellite tracking module.
"""

from unittest.mock import Mock, patch

from trmnl_satgus.calculate_position import SatelliteTracker, get_satgus_position


def test_satellite_tracker_initialization():
    """Test SatelliteTracker initialization."""
    tracker = SatelliteTracker()
    assert tracker is not None
    assert tracker.ts is not None
    assert tracker.earth is not None


def test_create_satellite_from_tle():
    """Test creating satellite from TLE data."""
    tracker = SatelliteTracker()

    # Sample TLE data
    name = "TEST SAT"
    line1 = "1 25544U 98067A   24001.50000000  .00016717  00000+0  31591-3 0  9993"
    line2 = "2 25544  51.6400 114.5000 0001000 110.5000 249.5000 15.50000000000000"

    satellite = tracker.create_satellite_from_tle(name, line1, line2)
    assert satellite is not None
    assert satellite.name == name


def test_get_satellite_position_structure():
    """Test that get_satellite_position returns expected structure."""
    tracker = SatelliteTracker()

    # Sample TLE data
    line1 = "1 25544U 98067A   24001.50000000  .00016717  00000+0  31591-3 0  9993"
    line2 = "2 25544  51.6400 114.5000 0001000 110.5000 249.5000 15.50000000000000"
    satellite = tracker.create_satellite_from_tle("TEST", line1, line2)

    position = tracker.get_satellite_position(satellite)

    # Check that all expected keys are present
    expected_keys = [
        "latitude",
        "longitude",
        "altitude_km",
        "velocity_km_s",
        "timestamp",
    ]
    for key in expected_keys:
        assert key in position

    # Check data types
    assert isinstance(position["latitude"], float)
    assert isinstance(position["longitude"], float)
    assert isinstance(position["altitude_km"], float)
    assert isinstance(position["velocity_km_s"], float)
    assert isinstance(position["timestamp"], str)


def test_get_distance_to_satellite():
    """Test distance calculation to satellite."""
    tracker = SatelliteTracker()

    # Sample TLE data
    line1 = "1 25544U 98067A   24001.50000000  .00016717  00000+0  31591-3 0  9993"
    line2 = "2 25544  51.6400 114.5000 0001000 110.5000 249.5000 15.50000000000000"
    satellite = tracker.create_satellite_from_tle("TEST", line1, line2)

    # Test distance calculation
    distance = tracker.get_distance_to_satellite(
        satellite, 40.7128, -74.0060
    )  # NYC coordinates

    assert isinstance(distance, float)
    assert distance > 0  # Distance should be positive


@patch("trmnl_satgus.calculate_position.SatelliteTracker")
def test_get_satgus_position(mock_tracker_class):
    """Test get_satgus_position function."""
    # Mock the tracker and its methods
    mock_tracker = Mock()
    mock_satellite = Mock()
    mock_position = {
        "latitude": 45.0,
        "longitude": -75.0,
        "altitude_km": 400.0,
        "velocity_km_s": 7.66,
        "timestamp": "2024-01-01T12:00:00+00:00",
    }

    mock_tracker.create_satellite_from_tle.return_value = mock_satellite
    mock_tracker.get_satellite_position.return_value = mock_position
    mock_tracker_class.return_value = mock_tracker

    # Test the function
    result = get_satgus_position()

    # Verify the result
    assert result == mock_position
    mock_tracker.create_satellite_from_tle.assert_called_once()
    mock_tracker.get_satellite_position.assert_called_once_with(mock_satellite, None)
