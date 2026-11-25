# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog], and this project adheres to
[Semantic Versioning].

## [Unreleased]

### Changed

- The GLORBs' arm waves move in single output steps (operator, 2026-11-24: "make a better animation
  for glorb"). Measured as the lamp plays the old file (WLED 16.0.1 Image effect on 23 ms draws,
  brightness 45, gamma 1.0): its 50 ms frames showed for 46 or 69 ms; its crests, cubed and then put
  through the 2.8 table, were lit above mid level for a fifth of each loop, under one LED wide; each
  LED sat dark for half the loop and moved by up to 10 counts (5 of the lamp's steps; 16.8 ΔL*, median
  10.1) a frame. Now: 86 frames of 2 cs, so the lamp shows each one for exactly one draw; a crest half
  a wave wide set in light over a glow of a quarter; one colour table per frame, so no level is rounded
  by the table; every LED moves by at most one step (2 counts; front 6.6 ΔL*, median 2.8). Same
  colours, same 2 s wave, same front and mirror. `tests/test_squid_gifs.py` checks the frame time
  against the lamp's draw time and the largest step on all 80 LEDs at the presets' brightness.
- No look GIF carries white or a pale colour any more (operator, 2026-11-23: "why the fuck is white in
  this?"; rule of 2026-11-18: "no white except it is white really selected"). Measured on each lamp's
  gamma, the pale share of non-black pixels was Squid Eyes 100 %, Ink Burst 46 %, Breathing 26 %,
  Chromatophores 13 %, Water 10 %, Deep Sea 2 %, the logo 4 % and the arm waves 3 to 15 %; now 0 %
  in every file. The eyes and highlights take the mark's gradient instead of the lavender `#b48cf5`,
  overlapping cells keep the brighter colour instead of adding up to white, and `mkgifs.py` holds every
  colour at least as saturated as `--violet` and refuses a pale colour table; `tests/test_squid_gifs.py`
  checks every committed GIF. Squid Plankton's third speck colour follows the drawing (red).
- TycStation on the Moon and the GLORBs is the website's theme (operator, 2026-11-23: "THeme of
  tycstation follfolws the website theme", "red blue"): button 7 plays `fleet/squid/tycstation-<size>.gif`
  there, the gradient running out and back along the lamp, and the curtain's logo is the mark in the same
  colours, one still frame. The couch (DJ Light) and the Exoys (Edge Colorwaves) keep their own looks on
  button 7. The GLORBs' port preset 1 moved from 7 to 19.
- The GLORBs' arm waves are drawn on the ball (operator, 2026-11-09: "a 'front' display and backside
  ambient"): each LED by its ring and longitude, the front display on two thirds of the ball, the back
  mirroring it at 35 %; their TycStation look the same way. Loop times, speeds and the ball's front are
  one `LOOK` block in `curtain/squid/draw.js`.
- A capture no longer carries the lamp's address or its Wi-Fi details: `wledlab.py capture` and
  `verify --save-captures` stamp firmware version, fps, power limit, palette count and state only.
  Scoring reads none of the dropped fields; older captures still load.
- `tools/check_private_lamp_data.py` reads content, not only paths: recordings in every capture format,
  compressed or renamed, device backups, MAC addresses, private network addresses, Wi-Fi names and
  coordinates are refused in the staged tree, in every commit of a push and of a pull request, and so
  is a branch that starts from the history before the recordings were removed. `make install-hooks`
  installs the push hook too. The factory config is checked by content like any other file.

- The remotes switch the HyperCube too (operator, 2026-11-20: "Pair cube"): `fleet/overlays/cube-gl015.json`
  turns ESP-NOW on and pairs the operator's three remotes, as the couch's and the Exoy lamps' overlays do.
  Its presets 1 to 4 are the cube's own looks; buttons 5 to 7 leave it as it is.
- The HyperCube takes an OTA upload from another subnet: `fleet/overlays/cube-gl015.json` sets
  `ota.same-subnet` false, as every other lamp's overlay does. tycpve's `wled:flash` uploads from the
  CI's subnet, which WLED refuses while the switch is true; tycpve's `wled:install` writes it through
  the cube's security form with its OTA password.
- The Exoy lamps run on DOMRAEM controllers with an I2S microphone since 2026-11-20 (operator:
  "switch over to them and make the other spares"): both overlays set AudioReactive's microphone,
  generic I2S on SD 26, WS 5, SCK 21, and sound sync off (`sync.mode` 0); until now they received
  the couch's sound sync (mode 2). The couch no longer sends it (`sync.mode` 0 in its overlay, was 1);
  no other controller received it. The two DOM-WLE-As that drove the lamps become TycLedSpare5 and
  TycLedSpare6: new overlays `fleet/overlays/spare5-domraem.json` and `spare6-domraem.json` (name,
  mDNS, syslog host, boots off at brightness 16, `ota.same-subnet` false). Host table and Spares
  section in `fleet/README.md`.
- The HyperCube boots off: new overlay `fleet/overlays/cube-gl015.json` with `def` `{ps: 0, on: false,
bri: 150}`, for tycpve `wled:install`. Until now it came up lit on its preset 1 when power returned.
- The Exoy lamps boot off (operator, 2026-11-19: "if we have power outage this happens and this an
  antipatern"): `def.on` is false in both overlays and the boot preset is the new 250, the calm
  cycle's playlist without power. A lamp stays dark after power comes back and shows the cycle's
  first look when someone switches it on. Until now both came up lit on playlist 20.
- The Exoy lamps' brightness is free across 1 to 255 (operator, 2026-11-19: "exoy brightness is
  artefact of stupid agent in the beginning. give full brightness range free."): no preset in
  `fleet/overlays/exoy-presets.json` sets `bri` any more (every look set 45 since 2026-11-11, the
  squid buttons 1 to 5 and 8 since 2026-11-18; the test patterns 30 and 31 set 60), so a recall, a
  remote button or a playlist step keeps the brightness the remote, the app or Home Assistant set.
  Every Exoy preset keeps `"on": true`, which now alone switches a lamp that is off back on. Both
  Exoy overlays set `if.sync.recv.bri` false, so a WLED controller sending sync in group 1 does not
  set their brightness. After power-on a lamp shows its `def.bri` (128, unchanged) until someone
  sets another. The couch, the Moon, the GLORBs and the curtain keep their looks' 45 and 200.
  `tests/test_presets.py` holds the presets' rules.

- Both Exoy lamps run at 40 FPS (`hw.led.fps` in both overlays, was 55), for image vid 2611190 and
  later (tyclab/tycExoyWled `293fde7`): that image asks WLED for a frame when the lamp's next one
  is due, as long as WLED's frame time (25 ms at 40 FPS) is no shorter than the scene's period
  (16.0 to 22.5 ms), so each scene is shown at its own rate. At 55 FPS WLED's own timer showed 54
  to 55 frames a second in every scene, with engine frames repeated or dropped. An older image
  must keep 55: at 40 it shows 40 of the engine's 44 to 62 frames a second.

- The Exoy lamps follow the remote's button rule like the couch, the Moon and the GLORBs (operator,
  2026-11-18: "fully integrate both into house modes etc. also on remotes"): presets 1 to 5 and 8 of
  `fleet/overlays/exoy-presets.json` play the squid's arm waves under the curtain's look names, from
  the new `fleet/squid/squid-arms-30x16.gif` (an Exoy lamp's 30×16 matrix, gamma 2.8) on one segment
  over the window lamp's columns X 0–29, at brightness 45. Presets 6 and 7 keep Edge Twinklefox and
  Edge Colorwaves. The looks that stood on 1 to 5 and 8 keep their names and fields in 23 to 28, and
  the boot playlist 20 ("Exoy calm cycle") plays the same ten looks in the same order.
  `tests/test_presets.py` holds the Exoys to the rule and checks that every playlist step names a
  preset. The other squid GIFs render byte-identical.

- Both Exoy lamps take their sound from the couch (operator, 2026-11-18: "they don't have mic use
  sound sharing"): the couch's overlay sends AudioReactive's UDP sound sync and both lamps' overlays
  receive it. The DOM-WLE-A has no microphone; with the PDM setting on 26/21 that both came with,
  AudioReactive read no sound. The lamps' overlays no longer set a squelch or microphone pins.

- The couch and both Exoy lamps pair three ESP-NOW remotes again. The third remote was
  unpaired on 2026-11-11 when its address was unknown. The two Exoy lamps' overlays turn
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

- `wledlab.py flash --usermods AudioReactive,Syslog`: the usermod settings blocks (`/json/cfg`
  `um`) the image carries. The lamp must then have exactly these after the flash; a block from
  before that is not among them may go with its usermod, and the tool names it. A declared block
  that is missing, or a block present that is not declared, is drift; inside a block that stays
  every value is compared as before. Without the option nothing changes: a block that goes is
  drift. For a controller whose image drops a usermod, such as Spare 4 going from the Exoy image
  `exoy_eth` (AudioReactive, Exoy, Syslog) back to `fleet_gledopto`, whose flash otherwise ends
  as "flash changed more than the firmware" on `um.Exoy` alone.
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
  offline `blackhole_model.py`, and the [12/12 gate measurements](glorb/experiments/acceptance.md).

### Fixed

- `wledlab.py install` no longer replaces a GIF under WLED's Image effect. The effect keeps the file it
  plays open (image_loader.cpp); a file replaced under that handle keeps its old bytes for it while its
  size is read from the path, so the decoder reads short at the old end, fails, and the segment stands on
  one frame until its name changes or it is reset (replayed on the host with the GLORB image's GIF
  library). A segment that plays a file about to change now gets another effect with no transition before
  the upload, which resets it also on a lamp that is off, and its look back afterwards. A preset check on
  a lamp that something else switched off again now fails with that reason instead of "1 different
  liveview frames": on 2026-11-24 a home automation switched a GLORB off about 70 ms after each recall. A
  preset that switches the lamp off itself (`"on": false`, the couch's boot layout) is left out of that.
- `wledlab.py install` recalls a preset once more when the lamp names another preset after the recall, and
  fails with that reason when it does so twice: on 2026-11-25 Home Assistant's theme rule set an Exoy lamp
  to its theme look one second after the recall of preset 125, and the reading was taken for that preset.
- `wledlab.py install` checks the name of every segment it puts back, the GIF an Image look plays. Two
  Image looks differ only in that name, and the check compared the effect fields alone, so a lamp left on
  the last recalled preset's GIF still read "look restored: OK" (reproduced with the repo's fake lamp).
  WLED 16.0.1 writes and reports the name (json.cpp), though its own `differs()` does not compare it.
- The GLORBs' looks face the room: their front display was centred on column 0, which faces the wall
  behind both balls (operator's optical test, 2026-11-24: "green atz wall directly behuind", "blue
  circles straight up front"), so the room saw the dimmed back. `LOOK.ball.front` is column 10 now;
  `squid-arms-20x6.gif` and `tycstation-20x6.gif` are their previous frames turned by 10 columns, pixel
  for pixel, and every other GIF is unchanged. Row 0 is the bottom ring ("red bottom blue top half fort
  both."); the looks are the same both ways up, so only the docs change for it.
- `wledlab.py install --cfg` restarts the lamp once when the write changes `nw.espnow`, `wifi.sleep`,
  `wifi.txpwr`, `id.mdns` or `id.inv`, which WLED 16 uses only when it connects, and puts back what the lamp
  showed. TycDodecaLinks and TycDodecaRechts came with ESP-NOW off, got it from their install on 2026-11-20
  and heard no remote press until they were restarted. While a live stream plays, such a write is refused
  before anything is written; the install ends red and names the settings.

- `wledlab.py flash` checks the image's release name itself, before anything is written, and tells
  the lamp to skip its own check. WLED 16.0.1 compares the uploaded name with the bytes that follow
  it on the stack (`bufToString` ends its copy at the buffer's end), so TycDodecaRechts refused an
  image of its own release on 2026-11-18 (`current='ESP32', uploaded='ESP32\xe9…'`), and the tool
  ended in a `UnicodeDecodeError` on that answer instead of reporting it. The refused upload had
  already reset the lamp's segments, which then show no colours or palettes until a restart. Now an
  image of another release, one that declares none, one whose description is newer than version 1
  (the lamp skips its whole check, and from version 2 on that check covers more than the name) or a
  missing file is refused before the upload; the lamp's answer is reported as text, before the undo
  begins; and after an upload that ends without the new firmware the lamp is restarted and gets its
  look back, whatever it answers on the way. A request whose answer was cut short is tried again
  like one that timed out.

- Both Exoy lamps run the engine at the original's pace and show every frame of it. Each scene has
  its own frame period (`um.Exoy.period_us` 0 with image vid 2611181, which carries the unchanged
  original's mean frame time per scene from the emulator: 18.4 to 19.9 ms for 67 scenes, 22.5 ms
  for Rhythm Run and Gloze); the image's single 16 ms was never measured and ran frame-driven motion
  about 16 % faster than the original's, 40 % in those two scenes. WLED runs at 55 FPS: at its
  default 42 FPS an effect is called every 23 ms, so a third of the engine's frames never reached
  the LEDs. Measured on TycDodecaRechts with one period of 18.5 ms, the step before: 54.1 engine
  frames a second against 55 shown, before 62.5 against 43.

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
