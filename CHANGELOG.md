# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]

### Added

- Repository gates mirrored from `tyclab/flakelab`: pre-commit suite (gitleaks, yamllint, markdownlint, prettier, ruff), CI jobs `lint`/`test`/`gitleaks`, issue forms, security policy, code of conduct.
- `make test`: offline tests of the palette emulation against known firmware values.
- Mirrored palettes fitted to the fork's 16-slot trajectory with the firmware's exact arithmetic (Colorwaves and Palette-effect layers separately).
- `wledlab.py verify`: acceptance gate on the lamps' current estimate, 70 s per preset.

### Fixed

- Black Hole – Sunset (preset 11): the fork's Intensity slider limits the stars to the first 40/255 of the palette (red to orange only) and its other sliders keep stock positions; the port palette carries that range stretched to 0–255, trail length now matches (19 vs 20 lit cells).
- Black Hole – Tertiary (preset 10): the fork's stars mix colours and drift through the palette together; rebuilt as white stars × a Palette colour layer over Tertiary 0–220 (sine dwell).
- Tartan – Analogous (preset 13): the fork adds its two line sets (crossings reach clip(2·colour)); the layer palette is boosted ×1.4 so the per-hue brightness matches.
- Frizzles (presets 7/9): fitted on sparkle shape (peak, lit count, histogram) and current together instead of current alone — `bri` 170/255 with blur 186/80 (preset 9 now peaks at 168 vs the fork's 177; preset 7 stays current-bound because stock draws 8 frizzles over 1.6× the cells).
- Hiphotic/Tartan colour layers: the fork's sine-driven palette index lingers at both palette ends; the layer palettes are fitted over the arcsine-warped sweep so the port spends the same time in each colour (Tartan – Analogous gets its own layer palette 189).
- Hiphotic pattern layers (presets 2/14): `c3` raised so the effect's raw time term breathes at the fork's ~7 s instead of 1.8 s — `activity` had matched while the sub-second variance share was 6× (preset 2) and 65× (preset 14) the fork's.
- Running – Analogous (preset 5): speed, wave and colour-cycle period measured on the lamps instead of scaled from preset 4 (the fork's Running colour cycle follows the effect speed: 35 s at preset 4, 18 s at preset 5).
- Fitted palettes weight the sweep's turning points, so the colour at each end of a cycle matches the fork (pure red at the Analogous end).
- Hiphotic – Tertiary pattern speed (`c3 12`, activity ratio 1.00) and a small spatial hue variation in both Hiphotic colour layers (the fork shows ~7° across the raster); Tartan colour layers fully uniform like the fork.
- Hiphotic – Fire: the fork only visits Fire indices 112–224 (dark red to orange, never black or yellow-white), so the Fire layer is fitted over that span (`mkpalettes.py` span).
- `analyse`/`compare` print `fast_share` (share of per-cell brightness variance above 1 Hz) and a hue census (share and brightness per 30° hue bin) next to the means.
- `analyse`/`compare` print `activity` (mean brightness change per lit cell per second) — the speed measure that also works for plasma and sparkle effects — and `stripe_period` (autocorrelation along the full middle rows) — the sinusoid `wavelength` snaps to whole stripes per ring on 20-cell rows; the hue-cycle autocorrelation works on the hue as a unit vector.

### Changed

- Frizzles/Black Hole use custom palettes with the 0.14 stop values (WLED 16 re-encodes its built-ins for gamma).
- Tartan composites draw plain white lines; Hiphotic floors 175/230 — brightness matched on current.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
