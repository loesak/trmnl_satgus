# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A TRMNL e-ink display plugin that tracks the SAT GUS satellite (NORAD 62713). There is no server. A GitHub Actions workflow precomputes a day of positions and pushes them to TRMNL as the plugin's **Static data**. The Liquid template picks the entry for each render's time and positions a world map (served from GitHub Pages) under a rotated rocket ("Gus").

## Data flow

1. `.github/workflows/fetch-tle.yml` (daily) runs `satgus/fetch_tle.py`, which pulls the TLE from Celestrak and commits `trmnl_data/satgus_tle.json` (`[skip ci]`).
2. `.github/workflows/publish-plugin.yml` runs hourly at :17, on pushes touching the plugin/Python/map data, and on dispatch. It has two jobs.
   - `map`: compares `render_map.map_version()` (a hash of the renderer and its GeoJSON) with the published `version.txt`. Only when they differ does it render `world.png` with `satgus/render_map.py` and deploy it to GitHub Pages (`https://loesak.github.io/trmnl_satgus/`).
   - `publish` (after `map`): `satgus/track.py` builds 24h of positions, one per minute, and writes them into `trmnl_plugin/src/settings.yml` as `static_data`. That happens only in CI and is never committed. Then it runs `trmnlp lint` and `trmnlp push --force` with the `TRMNL_API_KEY` secret.
3. TRMNL regenerates the plugin every refresh. `shared.liquid` computes `(trmnl.system.timestamp_utc - start) / step`, clamped to the track, to pick the current entry.

**Why it works this way:**
- GitHub runs scheduled workflows far less often than asked: about 5 a day for a `*/10` schedule, with gaps up to about 10h.
- TRMNL skips regenerating *polling* plugins whose data hasn't changed. Static plugins are exempt; we verified this with a throwaway static plugin.
- So a precomputed track pushed as static data stays current between runs. Don't switch back to polling a single position.

Static data shape (built by `track.build_track`): `{start, step, count, map_url, locations[], track[]}`. Each entry is `[world x px, world y px, heading°, altitude km×100, velocity km/s×100, location index or -1]`. Integers keep it near 41KB (TRMNL's limit is 100KB, and `trmnlp` warns at 75KB). The template formats values with integer math: two decimals, miles = ×0.621371, and the time as h:mm:ss AM/PM from the epoch. It avoids date filters, so the renderer's time zone can't matter. If you change the entry layout, change `track.py`, `shared.liquid` and `tests/test_track.py` together.

Consequences:
- `shared.liquid` (prepended to every layout) holds all CSS, Gus (an embedded webp), the map/rocket/title/footer markup (`{{ satgus_map }}`), and the formatted values. With no track data it shows "Waiting for orbit data". The four layouts only pick a `satgus--<layout>` class (Gus's `--gus-x/--gus-y`) and lay out their info box.
- **Never `trmnlp push` the committed `settings.yml` by hand.** Its `static_data` is empty, so the live plugin would show "Waiting for orbit data" until the next workflow run. To publish, run the workflow (`workflow_dispatch`), or inject a track first (see Commands).
- **World map:** Web Mercator at Leaflet zoom 3, i.e. the whole world is 2048×2048 CSS px (`WORLD_SIZE`), drawn at 2×.
  - `world_px(lat, lon)` gives a position's pixel on it. The template translates `.world` by `-x/-y` from Gus's spot, with west/center/east copies so it wraps across the antimeridian. Beyond about ±85° (the Mercator limit) it's blank.
  - Style: gray ocean, lightly tinted land, black 1:50m Natural Earth coastlines (`ne_50m_*.geojson`), and collision-checked labels.
  - The URL is versioned (`world.png?v=<map_version>`), so style changes bust caches.
  - We dropped CARTO tiles because they now need an API key.
  - The `<img>`s must keep `image-dither`. TRMNL's renderer (not CSS) dithers images with that class; without it, 1-bit screens lose the gray shading. Local `trmnlp serve` HTML previews don't dither, but its PNG renders do.
- `.satgus` fills the view with `overflow: hidden`, so mashups don't bleed. The plugin pins `framework_version: 3.4.3`.
- `calculate_position.py` (`SatelliteTracker`) is only a debugging CLI now; the plugin data comes from `track.py`, which repeats its altitude and heading math in vectorized form.
- Python modules find `trmnl_data/` with paths relative to `__file__` (three `dirname`s up), so scripts must stay at `trmnl_satgus/satgus/*.py`.

### Location lookup (`satgus/location_utils.py`)
Checks Natural Earth 110m GeoJSON files in `trmnl_data/` in priority order: country (`admin_0_countries`), then continent (`land`), then named ocean/sea (`geography_marine_polys`). It falls back to `{'location_type': 'unknown', 'location_name': None}`, and the templates display "Area 42" for that case. GeoDataFrames are lazily cached in module globals.

## Commands

Python project lives in `trmnl_satgus/` (Poetry, Python 3.13). Run from that directory:

```bash
poetry install
poetry run python satgus/fetch_tle.py            # refresh TLE (network: celestrak.org)
poetry run python satgus/calculate_position.py   # print the current position (debugging)
poetry run python satgus/track.py                # print a day's track as JSON
poetry run python satgus/track.py ../trmnl_plugin/src/settings.yml  # inject it as static_data (don't commit)
poetry run python satgus/render_map.py ../_site  # render world.png + version.txt
poetry run pytest tests/                         # all tests
poetry run pytest tests/test_track.py::test_build_track_shape  # single test
./pre-commit.sh   # full check: install, black, flake8, mypy, isort, bandit (-ll), pytest
```

Note: the README lists `trmnl_satgus/fetch_tle.py` paths, but the real scripts are under `satgus/`, which is how CI invokes them.

Style: black + isort (profile black), line length 88 (flake8 is configured to match). mypy runs with `ignore_missing_imports`.

Plugin preview, run from `trmnl_plugin/`: `trmnlp serve` (the TRMNL local preview tool; config in `.trmnlp.yml`, which watches `src/`).
For a local preview with real data: inject a track into `src/settings.yml` (see above), and add `asset_overrides` to `.trmnlp.yml` mapping the exact `map_url` (including `?v=…`) to a locally rendered `world.png`. To test a specific moment, override `variables: trmnl: system: timestamp_utc: <epoch>`. Revert both files afterwards (`git checkout trmnl_plugin/`).
Per-device renders: `trmnlp serve`, then `GET /render/<view>.png?screen_classes=<classes>&width=<px>&height=<px>&color_depth=<n>`. Width and height are **physical** pixels, CSS size × pixel ratio. For example, TRMNL X is `screen screen--v2 screen--lg screen--4bit` at 1872x1404, and OG is `screen screen--og screen--md screen--1bit` at 800x480. Requesting CSS size on a scaled device gives a cropped zoom. `trmnlp build --png --width/--height` only resizes the canvas and doesn't emulate devices. Run `trmnlp lint` before pushing.

## Tooling

- Dev Container (`.devcontainer/`), based on Debian trixie for ImageMagick 7 and non-snap Firefox ESR. It has Ruby 4 + `trmnlp` 0.32.3 (Firefox/geckodriver render PNGs: `trmnlp build --png --color-depth 1` writes true 1-bit, dithered renders to `_build/`) and pyenv Python 3.13 + Poetry. After changing the Dockerfile, IntelliJ may reuse its stale derived `jb-…-uid` image; delete that image and its container to force a real rebuild. `postCreate.sh` runs `poetry install` for every `pyproject.toml` and runs `pre-commit install -c pre-commit-config.yaml`. The container user mirrors the host user (name, UID, home), the repo is mounted at its host path, and `~/.claude` + `~/.claude.json` are bind-mounted from the host, so Claude Code sessions/memory/login are shared with the host (`claude --resume` works across both). Claude Code itself is installed in the image via the native installer. `~/.config/trmnlp` (the `trmnlp login` API key) is also bind-mounted from the host. `~/.ssh` is read-only, so the image bakes GitHub's host keys into `/etc/ssh/ssh_known_hosts`. A system git `pushInsteadOf` rule sends `https://github.com/` pushes over SSH; fetches stay HTTPS. `!`-prefixed commands in Claude Code have no stdin, so interactive prompts like `trmnlp login` must be run in a real terminal.
- The root `pre-commit-config.yaml` (no leading dot, so pass `-c` to pre-commit) runs generic YAML/TOML/whitespace hooks. For any change under `trmnl_satgus/`, it also runs `trmnl_satgus/pre-commit.sh`.
