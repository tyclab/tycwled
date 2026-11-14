# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]

### Changed

- The curtain's seven remote buttons now show Breathing, Ink Burst, Deep Sea,
  Chromatophores, Water, PS Fuzzy Noise and TycStation, in that order. Eyes
  remains in slot 8; the duplicate Fuzzy Noise is removed. Companion lamps
  match the squid slots and keep every native look.
- Installing reordered presets preserves the displayed look with its new preset
  number, or clears that marker if the look was removed.

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
- The curtain's ledmap places every string at its measured position: one
  square cell per door-panel string spacing, LED rows at the measured 1.66×
  that spacing, all panels level. 68 × 42 cells, 1560 mapped; `mkledmap.py`
  carries the measured positions.

### Removed

- The TycStation palette as custom palette files (`fleet/tycstation/`: slot 0 for the curtain,
  the couch and the Moon, slot 6 for the GLORBs) with their generator, their `check-palettes`
  step and `install`'s slot check for a palette sent with `--file`. Every lamp runs a build whose
  usermod registers the same stops as palette 255 ("TycStation 0"), and no preset used the files.

### Added

- `usermods/tycstation_fx/`: the squid patterns as WLED 16 effects for every fleet build. Squid
  Arms (the arm waves), Squid Skin (the chromatophore cells) and Squid Plankton (the deep-sea
  water) run on 1D and 2D segments of any size, follow AudioReactive's volume through a Sound
  slider and keep moving in silence. The usermod registers the TycStation palette as usermod
  palette 255, and on a lamp with colour gamma off (the GLORBs) encodes its pixels and the palette
  with WLED's 2.8 table, so every lamp puts the same values on the wire. Tests render the
  patterns on the host against the committed squid GIFs. On the Moon, the couch, the curtain and
  both GLORBs since release fleet-20261110-90019c5.
- Curtain: six squid loops as animated GIFs for the Image effect, drawn from the TycStation
  mark by `curtain/squid/mkgifs.py` (presets 4 to 9: Squid Breathing, Squid Ink Burst,
  Squid Deep Sea, Squid Eyes, Squid Chromatophores, Squid Water; no blur, brightness 160).
  Each loop is a sequence of stages (hover, jet, glide, wave; swim in, burst, dart, burst
  again; and so on) with motion several LEDs wide. Squid Breathing tours the four corners,
  reaching every edge of the curtain. Squid Water is the skin cells as slow water, swells
  rolling through them, with the squid drifting through as a dark shape.
- The squid's arm waves for the other lamps, as GIFs for the Image effect at each lamp's own size
  (`fleet/squid/`: 300x1 for the couch strip, 20x6 for a GLORB, 8x8 for the Moon): the mark's
  gradient along the row, blue end to red end, with waves running outward from the middle.
  Drawn by the same `curtain/squid/mkgifs.py`. The GLORB file is encoded for their output gamma
  of 1.0, so all lamps put the same values on the wire.
- `install` skips files and presets the lamp already holds and recalls presets only when they or a
  file they show changed, so adding a file leaves the look alone.
- `wledlab.py install --remove-palette <slot>` takes a custom palette off a lamp with WLED's
  `rmcpal` request, repeats it until the file is gone and checks that the lamp's palette list
  followed.
- `wledlab.py install --file` uploads other files (GIFs) and reads them back, checks that an
  uploaded animated GIF moves in liveview, and `--restore` puts the lamp's look back afterwards.
  A preset mismatch now makes `install` exit non-zero.
- Curtain: the TycStation logo GIF and the controller's presets (preset 1 "TycStation",
  the Image effect on the segment named `tycstation.gif`).
- Curtain: presets 2 and 3 "PS Fuzzy Noise", the operator's pick of 2026-10-07 (palette
  Ocean, Speed 62, Particles 26, Bounce 104, Friction 67, Scale 5, Collide on, brightness
  28). hatyc's Evening look of that name recalls preset 3.

- `usermods/syslog_events/`: boot with reset reason and the previous run's last
  breadcrumb, a panic-hook crash record with backtrace, Wi-Fi loss/reconnect with
  RSSI and reason, heap-low crossings, OTA, WLED error codes and an hourly status
  line, as RFC3164 over UDP, rate-limited and kept off the LED output path.
- `usermods/syslog_events/`: a `live override: <old> -> <new>` line on every change
  of WLED's live override (`lor`), warning while set, naming the request path, and
  `lor=` at the end of the status line: a lamp ignoring its live stream shows in Loki.
- `curtain/`: configuration overlay and ledmap for the three-panel H70B5
  curtain on the Gledopto GL-C-618WL, with the generator `mkledmap.py`; `make lint`
  checks the committed map against it.
- `fleet/`: build envs for our four lamps (stock-equivalent `ESP32` plus syslog for
  the Couch strip and the Moon, `glorb_port` plus syslog for the GLORBs) and
  `fleet/build.sh`.
- `wledlab.py flash`: OTA with a before-snapshot, then fails on any cfg change
  beyond the build stamp and a new usermod block, or any presets change.
- `wledlab.py verify`: structural acceptance gate (brightness histogram, hue
  EMD, saturation, spatial structure, activity, peak, lit cells, mean V,
  current ratio) over a simultaneous 100 s window per preset; refuses
  unhealthy captures and re-measures them; `rescore` re-runs the same
  criteria offline over saved captures.
- `glorb/experiments/2026-08-31-reversing/`: the disassembly notes, the
  offline `blackhole_model.py`, and the committed 12/12 gate log
  (`verify-2026-09-01-holes.log`).

### Fixed

- GLORB Running now advances the spatial phase before its first sine sample,
  matching the original loop. The correction removes a one-cell brightness-wave
  offset while preserving the phase saved between frames.
- `fleet/` builds apply `patches/frozen-segment-reset.patch`: on WLED 16 a `/json/state`
  request that changes the effect and sets pixels with `i` left the segment frozen and black,
  and an effect change blanked a frozen segment. The reset now waits until the segment is
  unfrozen.
- `wledlab.py install --restore` and `flash` put the look back with the preset it was: the
  request names the preset (`pd`) and uses the one-shot transition (`tt`). Before, the lamp
  reported no preset afterwards, so Home Assistant lost the curtain's look and ended the squid
  scene while the squid still played, and `transition: 0` stayed as the lamp's setting.
- Fleet releases cut on one day get different build stamps (`YYMMDDn`). Both would have been
  `YYMMDD0`, and `wled:flash` proves the flashed image by that stamp.
- Remote button 2 no longer switches the couch strip off: the couch's boot
  layout moved from preset 2 to 250, out of the slots the remote's number
  buttons call. The `fleet/remote.json` map and `install --remote` added with
  it are gone again: they rested on a fallback effect WLED 16.0.1 never shows,
  and the map cost the re-press of a current preset and the end of night mode.
- `verify` refuses a non-positive `--samples` or `--interval` before it touches
  either lamp, instead of switching both through every preset and failing each
  on an empty sample window.
- `install --cfg` replaces the README's bare `curl` of `cfg-overrides.json`.
  WLED 16 clears every paired ESP-NOW remote on a `/json/cfg` write without an
  `nw` block (`cfg.cpp`, since PR 4654); the new step carries the lamp's
  `espnow` flag and remote list along and reads each override back.

- **The lamp's microphone works on the port.** The build override sets
  `-D I2S_USE_16BIT_SAMPLES`. With WLED's default 32-bit samples the S3's PDM
  mic reported `quiet` with AGC pinned at `1.00 x` and the sound-reactive
  effects rendered black. The mechanism is not proven; the 32→16-bit
  conversion is a float divide and does not zero samples by itself. Confirmed
  on both lamps against an independent sound-level meter: AGC-vs-dBA
  correlation -0.903 on a patched lamp, against -0.968 for a known-good
  reference microphone and no signal at all on an unpatched one.

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
