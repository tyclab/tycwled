# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]

### Changed

- **The port is a reimplementation now, not an approximation.** The six fork
  effects (Colorwaves, Running, Frizzles, Black Hole, Hiphotic, Tartan) were
  disassembled out of the factory firmware image and rebuilt as the WLED 16
  usermod `glorb/usermod/glorb_fx/`, with the fork's FastLED arithmetic
  (sin8/sin16 tables, `+1` scaling, 0.14 `color_blend`, direct
  `fadeToBlackBy`, row-then-column `blur2d`) carried verbatim. Everything the
  previous entries here described — fitted palettes, white-star composites,
  layer palettes, boosted `bri` — is gone; see the git history for that era
  and the README for why it never converged.
- The six palettes the factory presets use ship as custom palettes 200–195
  with the factory stop values verbatim (WLED regenerated its built-in
  gradients after 0.14; only Atlantica survived byte-identical).
- The port runs `light.gc` 1.0: 0.14.4 never gamma-corrects rendered effect
  output, WLED 16 gammas the whole frame in `show()`.
- The usermod gates every pixel access on the ledmap (`glorb_cellMapped`):
  0.14.4 gives unmapped raster cells no storage, and losing that topology made
  the blurred effects light 20–30 % extra dim cells.

### Added

- `wledlab.py verify`: structural acceptance gate (brightness histogram, hue
  EMD, saturation, spatial structure, activity, peak, lit cells, mean V,
  current ratio) over a simultaneous 100 s window per preset; refuses
  unhealthy captures and re-measures them; `rescore` re-runs the same
  criteria offline over saved captures.
- `glorb/experiments/2026-08-31-reversing/`: the disassembly notes, the
  offline `blackhole_model.py`, and the committed 12/12 gate log
  (`verify-2026-09-01-holes.log`).

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
