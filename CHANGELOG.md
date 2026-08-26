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

### Changed

- Frizzles/Black Hole use custom palettes with the 0.14 stop values (WLED 16 re-encodes its built-ins for gamma).
- Tartan composites draw plain white lines; Hiphotic floors 175/230 — brightness matched on current.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
