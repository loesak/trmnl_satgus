# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A TRMNL e-ink display plugin that tracks the SAT GUS satellite (NORAD 62713). There is no server: GitHub Actions run the Python code on a schedule and commit JSON into `trmnl_data/`, and TRMNL polls the raw GitHub URL of that JSON to render a Liquid template.

## Data flow

1. `.github/workflows/fetch-tle.yml` (daily, 00:00 UTC) runs `satgus/fetch_tle.py`, which pulls the TLE from Celestrak and writes `trmnl_data/satgus_tle.json`.
2. `.github/workflows/fetch-position.yml` (every 10 min) runs `satgus/calculate_position.py`, which propagates the cached TLE with skyfield, then writes `trmnl_data/satgus_position.json`. It also computes the heading (bearing between the subpoint now and 1s later) and the location label (see below). The same job then runs `satgus/render_map.py`, which draws the basemap PNG centered on the satellite, deploys it to GitHub Pages (`https://loesak.github.io/trmnl_satgus/map.png`), and only then commits the JSON. The JSON's `map_url` carries a `?t=<timestamp>` cache-buster, so it never points at a stale map.
3. The TRMNL plugin (`trmnl_plugin/src/settings.yml`, `strategy: polling`) fetches `https://raw.githubusercontent.com/loesak/trmnl_satgus/refs/heads/main/trmnl_data/satgus_position.json` every 15 min, and the Liquid templates interpolate its top-level keys (`{{ latitude }}`, `{{ heading_degrees }}`, …) and show `{{ map_url }}` as an `<img>` centered under a rotated rocket icon. The plugin pins `framework_version: 3.4.3` in `settings.yml`.

Consequences:
- **The keys in `satgus_position.json` are the contract with the templates.** Rename or add a field in `SatelliteTracker.get_satellite_position` only together with the templates. TRMNL prepends `shared.liquid` to every layout. It holds all CSS, Gus (an embedded webp, once), the map/rocket/title/footer markup (`{{ satgus_map }}`), and the formatted values (`location`, `updated_at`, `gus_rotation`, `*_fixed` two-decimal numbers). It uses Liquid, not JS. The four layouts (`full`, `half_horizontal`, `half_vertical`, `quadrant`) only pick a `satgus--<layout>` class (Gus position) and lay out their info box.
- Most commits on `main` are bot commits ("Update satellite position [skip ci]"). Pull before pushing, and don't hand-edit `satgus_tle.json` or `satgus_position.json` unless you are testing on purpose.
- **Map rendering.** The map is a pre-rendered image, not live tiles: CARTO tiles now require an API key, and TRMNL's screenshot didn't reliably wait for tiles to load. `render_map.py` draws Web Mercator at Leaflet zoom 3, 2048x1792 CSS px at 2x. That size covers the largest TRMNL-supported screen (1371x1028 CSS, either orientation) from every layout's off-center Gus position, and it must match `.satgus .map` in `shared.liquid`. When changing the size, deploy the Python first and let the workflow publish the new map before pushing templates, or the live map is stretched. The style is gray ocean, lightly tinted land, and black 1:50m Natural Earth coastlines (`ne_50m_*.geojson`), with collision-checked labels kept clear of the rocket. It handles antimeridian wrap. `.satgus` fills the view with `overflow: hidden`, so mashups don't bleed. The map and Gus both center on the layout's `--gus-x`/`--gus-y`, so they always line up. The `<img>` must keep the `image-dither` class. TRMNL's renderer (not CSS) dithers images with that class; without it, 1-bit screens round every gray to black or white and the ocean/land shading disappears. Local `trmnlp` previews don't dither, so check shading on the TRMNL dev UI or a device.
- Python modules find `trmnl_data/` with paths relative to `__file__` (three `dirname`s up), so scripts must stay at `trmnl_satgus/satgus/*.py`.

### Location lookup (`satgus/location_utils.py`)
Checks Natural Earth 110m GeoJSON files in `trmnl_data/` in priority order: country (`admin_0_countries`), then continent (`land`), then named ocean/sea (`geography_marine_polys`). It falls back to `{'location_type': 'unknown', 'location_name': None}`, and the templates display "Area 42" for that case. GeoDataFrames are lazily cached in module globals.

## Commands

Python project lives in `trmnl_satgus/` (Poetry, Python 3.13). Run from that directory:

```bash
poetry install
poetry run python satgus/fetch_tle.py            # refresh TLE (network: celestrak.org)
poetry run python satgus/calculate_position.py   # compute + write position JSON
poetry run python satgus/render_map.py ../_site  # render map.png for the saved position
poetry run pytest tests/                         # all tests
poetry run pytest tests/test_satellite.py::test_create_satellite_from_tle  # single test
./pre-commit.sh   # full check: install, black, flake8, mypy, isort, bandit (-ll), pytest
```

Note: the README lists `trmnl_satgus/fetch_tle.py` paths, but the real scripts are under `satgus/`, which is how CI invokes them.

Style: black + isort (profile black), line length 88 (flake8 is configured to match). mypy runs with `ignore_missing_imports`.

Plugin preview, run from `trmnl_plugin/`: `trmnlp serve` (the TRMNL local preview tool; config in `.trmnlp.yml`, which watches `src/`).
To preview an unpublished map locally: render with `poetry run python satgus/render_map.py <dir>`, serve that directory over HTTP, and temporarily set `variables:` in `.trmnlp.yml` (position fields plus `map_url`). Don't commit those overrides. `asset_overrides` in `.trmnlp.yml` can map `https://loesak.github.io/trmnl_satgus/map.png` to a local file, but it matches exact URLs, so also pin `map_url` to that URL without `?t=`.
Per-device renders: `trmnlp serve`, then `GET /render/<view>.png?screen_classes=<classes>&width=<px>&height=<px>&color_depth=<n>`. Width and height are **physical** pixels, CSS size × pixel ratio. For example, TRMNL X is `screen screen--v2 screen--lg screen--4bit` at 1872x1404, and OG is `screen screen--og screen--md screen--1bit` at 800x480. Requesting CSS size on a scaled device gives a cropped zoom. `trmnlp build --png --width/--height` only resizes the canvas and doesn't emulate devices. Run `trmnlp lint` before pushing.

## Tooling

- Dev Container (`.devcontainer/`), based on Debian trixie for ImageMagick 7 and non-snap Firefox ESR. It has Ruby 4 + `trmnlp` 0.32.3 (Firefox/geckodriver render PNGs: `trmnlp build --png --color-depth 1` writes true 1-bit, dithered renders to `_build/`) and pyenv Python 3.13 + Poetry. After changing the Dockerfile, IntelliJ may reuse its stale derived `jb-…-uid` image; delete that image and its container to force a real rebuild. `postCreate.sh` runs `poetry install` for every `pyproject.toml` and runs `pre-commit install -c pre-commit-config.yaml`. The container user mirrors the host user (name, UID, home), the repo is mounted at its host path, and `~/.claude` + `~/.claude.json` are bind-mounted from the host, so Claude Code sessions/memory/login are shared with the host (`claude --resume` works across both). Claude Code itself is installed in the image via the native installer. `~/.config/trmnlp` (the `trmnlp login` API key) is also bind-mounted from the host. `~/.ssh` is read-only, so the image bakes GitHub's host keys into `/etc/ssh/ssh_known_hosts`. A system git `pushInsteadOf` rule sends `https://github.com/` pushes over SSH; fetches stay HTTPS. `!`-prefixed commands in Claude Code have no stdin, so interactive prompts like `trmnlp login` must be run in a real terminal.
- The root `pre-commit-config.yaml` (no leading dot, so pass `-c` to pre-commit) runs generic YAML/TOML/whitespace hooks. For any change under `trmnl_satgus/`, it also runs `trmnl_satgus/pre-commit.sh`.
