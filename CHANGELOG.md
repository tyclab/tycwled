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

- Running – Analogous (preset 5): speed, wave and colour-cycle period measured on the lamps instead of scaled from preset 4 (the fork's Running colour cycle follows the effect speed: 35 s at preset 4, 18 s at preset 5).
- Fitted palettes weight the sweep's turning points, so the colour at each end of a cycle matches the fork (pure red at the Analogous end).
- Hiphotic – Tertiary pattern speed (`c3 12`, activity ratio 1.00) and a small spatial hue variation in both Hiphotic colour layers (the fork shows ~7° across the raster); Tartan colour layers fully uniform like the fork.
- Hiphotic – Fire: the fork's colour cycle never goes below brightness ~117, so the Fire layer is fitted over that range only (`mkpalettes.py` floor); the pattern layer keeps its contrast instead of a 230 grey floor.
- `analyse`/`compare` print `activity` (mean brightness change per lit cell per second) — the speed measure that also works for plasma and sparkle effects — and `stripe_period` (autocorrelation along the full middle rows) — the sinusoid `wavelength` snaps to whole stripes per ring on 20-cell rows; the hue-cycle autocorrelation works on the hue as a unit vector.

### Changed

- Frizzles/Black Hole use custom palettes with the 0.14 stop values (WLED 16 re-encodes its built-ins for gamma).
- Tartan composites draw plain white lines; Hiphotic floors 175/230 — brightness matched on current.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
