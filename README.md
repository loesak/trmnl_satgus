# Satgus Terminal

A vanilla Poetry Python project with satellite tracking capabilities.

## Features

- **Satellite Tracking**: Track satellite positions using TLE (Two-Line Element) data
- **SATGUS Tracking**: Built-in SATGUS satellite position tracking
- **Distance Calculations**: Calculate distance from observer to satellite
- **Pass Predictions**: Predict satellite passes over specific locations

## Development Setup

This project uses Dev Containers for development. To get started:

1. Open the project in VS Code
2. When prompted, click "Reopen in Container" to open the project in a dev container
3. The container will automatically install Poetry and set up the development environment

## Project Structure

```
satgus-trmnl/
├── .devcontainer/          # Dev container configuration
├── trmnl_satgus/          # Main package
│   ├── __init__.py
│   ├── calculate_position.py # Satellite position calculation
│   └── fetch_tle.py       # TLE data fetching
├── trmnl_data/            # Data files
│   ├── satgus_tle.json    # TLE data
│   └── satgus_position.json # Satellite position data
├── trmnl_plugin/          # Plugin files
│   ├── markup.html        # HTML template
│   └── gusrocket.webp    # Rocket image
├── tests/                 # Test files
│   └── test_satellite.py  # Tests for position calculation
├── pyproject.toml         # Poetry configuration
└── README.md
```

## Available Commands

Once inside the dev container, you can use the following Poetry commands:

- `poetry install` - Install dependencies
- `poetry run python trmnl_satgus/calculate_position.py` - Run the satellite position calculator
- `poetry run pytest` - Run tests
- `poetry run black .` - Format code with Black
- `poetry run flake8 .` - Lint code with Flake8
- `poetry run isort .` - Sort imports with isort

## Satellite Tracking Usage

### Basic Usage

```python
from trmnl_satgus.calculate_position import SatelliteTracker, get_satgus_position

# Get current SATGUS position
satgus_position = get_satgus_position()
print(f"SATGUS is at {satgus_position['latitude']:.2f}°N, {satgus_position['longitude']:.2f}°E")

# Create a custom satellite tracker
tracker = SatelliteTracker()

# Create satellite from TLE data
satellite = tracker.create_satellite_from_tle(
    "MY_SAT",
    "1 25544U 98067A   24001.50000000  .00016717  00000+0  31591-3 0  9993",
    "2 25544  51.6400 114.5000 0001000 110.5000 249.5000 15.50000000000000"
)

# Get satellite position
position = tracker.get_satellite_position(satellite)

# Calculate distance from observer
distance = tracker.get_distance_to_satellite(satellite, 40.7128, -74.0060)  # NYC
```

### Features

- **Real-time Position Tracking**: Get current satellite positions
- **Historical Data**: Calculate positions for specific times
- **Distance Calculations**: Find distance from any location to satellite
- **Pass Predictions**: Predict when satellites will be visible from your location

## Dependencies

The project uses:
- **skyfield**: Astronomical calculations and satellite tracking
- **numpy**: Numerical computations
- **requests**: HTTP requests for data fetching

## Development

The project includes:
- **pytest** for testing
- **black** for code formatting
- **flake8** for linting
- **isort** for import sorting

All tools are configured to work together seamlessly. 