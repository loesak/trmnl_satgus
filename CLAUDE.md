# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A TRMNL e-ink display plugin that tracks the SAT GUS satellite (NORAD 62713). There is no server: GitHub Actions run the Python code on a schedule and commit JSON into `trmnl_data/`, and TRMNL polls the raw GitHub URL of that JSON to render a Liquid template.

## Data flow

1. `.github/workflows/fetch-tle.yml` (daily, 00:00 UTC) runs `satgus/fetch_tle.py`, which pulls the TLE from Celestrak and writes `trmnl_data/satgus_tle.json`.
2. `.github/workflows/fetch-position.yml` (every 10 min) runs `satgus/calculate_position.py`, which propagates the cached TLE with skyfield, then writes `trmnl_data/satgus_position.json`. It also computes the heading (bearing between the subpoint now and 1s later) and the location label (see below).
3. The TRMNL plugin (`trmnl_plugin/src/settings.yml`, `strategy: polling`) fetches `https://raw.githubusercontent.com/loesak/trmnl_satgus/refs/heads/main/trmnl_data/satgus_position.json` every 15 min, and the Liquid templates interpolate its top-level keys (`{{ latitude }}`, `{{ heading_degrees }}`, …) into a Leaflet map with a rotated rocket icon.

Consequences:
- **The keys in `satgus_position.json` are the contract with the templates.** If you rename or add a field in `SatelliteTracker.get_satellite_position`, update every layout (`full`, `half_horizontal`, `half_vertical`, `quadrant`). Each one is a standalone copy of the markup/JS; `shared.liquid` is effectively empty, and `full.liquid.backup` is an old copy.
- Most commits on `main` are bot commits ("Update satellite position [skip ci]"). Pull before pushing, and don't hand-edit `satgus_tle.json` or `satgus_position.json` unless you are testing on purpose.
- Python modules find `trmnl_data/` with paths relative to `__file__` (three `dirname`s up), so scripts must stay at `trmnl_satgus/satgus/*.py`.

### Location lookup (`satgus/location_utils.py`)
Checks Natural Earth 110m GeoJSON files in `trmnl_data/` in priority order: country (`admin_0_countries`), then continent (`land`), then named ocean/sea (`geography_marine_polys`). It falls back to `{'location_type': 'unknown', 'location_name': None}`, and the templates display "Area 42" for that case. GeoDataFrames are lazily cached in module globals.

## Commands

Python project lives in `trmnl_satgus/` (Poetry, Python 3.13). Run from that directory:

```bash
poetry install
poetry run python satgus/fetch_tle.py            # refresh TLE (network: celestrak.org)
poetry run python satgus/calculate_position.py   # compute + write position JSON
poetry run pytest tests/                         # all tests
poetry run pytest tests/test_satellite.py::test_create_satellite_from_tle  # single test
./pre-commit.sh   # full check: install, black, flake8, mypy, isort, bandit (-ll), pytest
```

Note: the README lists `trmnl_satgus/fetch_tle.py` paths, but the real scripts are under `satgus/`, which is how CI invokes them. `tests/test_satellite.py` imports from `trmnl_satgus.calculate_position`, but the package is `satgus`, so expect that import to need fixing before the tests pass.

Style: black + isort (profile black), line length 88 (flake8 is configured to match). mypy runs with `ignore_missing_imports`.

Plugin preview, run from `trmnl_plugin/`: `trmnlp serve` (the TRMNL local preview tool; config in `.trmnlp.yml`, which watches `src/`).

## Tooling

- Dev Container (`.devcontainer/`). `postCreate.sh` runs `poetry install` for every `pyproject.toml` and runs `pre-commit install -c pre-commit-config.yaml`. The container user mirrors the host user (name, UID, home), the repo is mounted at its host path, and `~/.claude` + `~/.claude.json` are bind-mounted from the host, so Claude Code sessions/memory/login are shared with the host (`claude --resume` works across both). Claude Code itself is installed in the image via the native installer.
- The root `pre-commit-config.yaml` (no leading dot, so pass `-c` to pre-commit) runs generic YAML/TOML/whitespace hooks. For any change under `trmnl_satgus/`, it also runs `trmnl_satgus/pre-commit.sh`.
