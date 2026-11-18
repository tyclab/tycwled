# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]

### Changed

- Both Exoy lamps take their sound from the couch (operator, 2026-11-18: "they don't have mic use
  sound sharing"): the couch's overlay sends AudioReactive's UDP sound sync and both lamps' overlays
  receive it. The DOM-WLE-A has no microphone; with the PDM setting on 26/21 that both came with,
  AudioReactive read no sound. The lamps' overlays no longer set a squelch or microphone pins.

- The couch and both Exoy lamps pair three ESP-NOW remotes: `704bcaca4b78` is the operator's third
  remote again (unpaired on 2026-11-11 as an unknown address). The two Exoy lamps' overlays turn
  ESP-NOW on; their controllers came with it off and heard no remote.

- Each Exoy ONE lamp has its own controller (operator, 2026-11-18): TycDodecaLinks (left lamp,
  kitchen end) and TycDodecaRechts (right lamp, window end), the DOMRAEM DOM-WLE-As that were
  Spares 1 and 2. Their overlays `fleet/overlays/exoy-links-domraem.json` and
  `exoy-rechts-domraem.json` hold one output of 480 LEDs on GPIO 16 limited to 6000 mA, a 30×16
  matrix, gamma 2.8, AudioReactive on and boot preset 20. The black GL-C-618WL that drove both
  lamps (TycDodeca) becomes Spare 4, `fleet/overlays/spare4-gledopto.json`; Spare 3 is named
  TycLedSpare3. `exoy-gledopto.json`, `spare1-domraem.json` and `spare2-domraem.json` are removed.

- The lamps in service carry TycStation names as `id.name`, the name the WLED app shows: TycCouch,
  TycMoon, TycGlorbLinks, TycGlorbRechts, TycCurtain and TycDodeca. The Moon and the GLORBs get
  overlays that hold only the name (`fleet/overlays/moon.json`, `glorb-links.json`,
  `glorb-rechts.json`). Hosts, mDNS names and the spares' names stay.
- The couch overlay receives no WLED UDP sync, as the couch has since 2026-11-06, and the curtain
  overlay puts output 2 on GPIO 4 and output 3 on GPIO 12, as the curtain runs: writing either
  overlay changes nothing on its lamp but the name (the curtain's sync receive of brightness goes
  off, with no receive group set).
- The controller of the two dodecahedron lamps limits each output to 6500 mA instead of 6000 mA
  (`fleet/overlays/exoy-gledopto.json`): both lamps run on one 5 V 12 A supply since 2026-11-17.
- That controller plays its preset 20 ("Exoy calm cycle", a playlist of stock looks) after
  power-on instead of preset 1, one plain colour.
- `wledlab.py flash --cfg-migration 0.15-to-16.0.1` also accepts a classic ESP32 on WLED 0.15.4
  (Gledopto's factory firmware on a GL-C-015WL reports it). The prediction is unchanged:
  v0.15.3..v0.15.4 changes no `cfg.cpp`, `json.cpp` or `set.cpp`, and that controller's stored cfg
  has the key paths of the reviewed 0.15.1 snapshot (`fleet/README.md`, Flash). One 0.15.4
  controller has been flashed with it, once: on 2026-11-17 the GL-C-015WL went from its factory
  0.15.4 image (vid 2508020) to a 16.0.1 image (release `ESP32`, an env that extends `fleet_esp32`)
  at 3d331d6; the tool reported `cfg: matches reviewed migration | presets.json: byte-identical`,
  and the controller came back as 16.0.1, release `ESP32`. Other 0.15 versions are still refused
  before upload.
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

- `wledlab.py install --cfg` accepts a remote list the overlay names: it checks it like every other key
  instead of reporting the change as dropped remotes (TycDodecaLinks, 2026-11-18: a new controller got
  its three remotes from its overlay and the install ended red). A list the write dropped still fails it.

- `wledlab.py install --cfg` sets a locked controller's OTA switches (`ota.lock`, `lock-wifi`, `aota`,
  `same-subnet`) through the security form with the OTA password. WLED 16.0.1 hears them in a
  `/json/cfg` body only with the OTA lock off (`cfg.cpp`), so on a locked controller the write
  ended with `cfg: MISMATCH` although everything else had landed.
- GLORB effects preserve the original palette interpolation, brightness scaling
  and nonwrap index arithmetic when built against WLED 16.
- GLORB Black Hole, Frizzles and Tartan add pixels with the original rounding:
  on overflow each channel becomes `v*255/max`. WLED 16's ratio-preserving add
  landed one step lower (Tartan: 254 where the original code renders 255).
- GLORB Black Hole no longer reads its first checkbox, which the original ignores:
  with palette 0 its stars take the primary colour whether or not it is ticked.

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
