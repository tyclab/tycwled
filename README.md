# tycwled

Tools and data for putting the GLORB look back onto stock WLED 16, plus a way
back to the factory firmware. Made for our own two lamps, published so other
GLORB owners can do the same, check our numbers on their lamps, and improve on
them. We think the port is close; you are the judge — open an issue with what
you see, or a pull request with what you changed.

## GLORB owners: start here

You need: a computer on the same network as the lamps (Python ≥ 3.10, `make`,
`curl`; nothing to install), the lamps' IP addresses (router DHCP list, the
WLED app, or `http://wled-<xxxxxx>.local`), and for `verify`/`compare` a
second GLORB still on the factory firmware with its factory presets 1–14.
"ref" below is that factory lamp, "target" the one on stock WLED 16.

Flashing stock WLED onto a GLORB keeps the hardware working but loses the
fork's spherical effects (IDs 189–198, flag `g`) — they live in closed
firmware, not in the ledmap. Two ways out, both in this repo:

- **Stay on stock WLED 16 and get the factory look back** (what
  `glorb/wled16-port/` is): upload `ledmap.json`, `presets.json` and
  `palette0..10.json` byte-exact, then post `cfg-overrides.json` to
  `/json/cfg`:
  `python3 wledlab.py install --host <lamp> --ledmap glorb/wled16-port/ledmap.json --presets glorb/wled16-port/presets.json $(for n in $(seq 0 10); do echo --palette glorb/wled16-port/palette$n.json; done)`
  and `curl -X POST -H 'Content-Type: application/json' --data @glorb/wled16-port/cfg-overrides.json http://<lamp>/json/cfg`.
  Fidelity, measured against a factory lamp: Colorwaves and Running match in
  motion, wavelength, hue range and brightness; Hiphotic/Tartan are rebuilt
  as two-segment composites (see below); Frizzles/Black Hole keep the stock
  algorithm with the factory hues and matched brightness — the fork's
  softer sparkle is not reproducible without its code.
- **Go back to the factory firmware**: the images are in SNRGY's
  [GLORB-WebInstaller](https://github.com/snrgy-studios/GLORB-WebInstaller)
  (`bin/GLORB_0_14_4-1_3/firmware_gma_83.bin`). From WLED 16 upload it at
  `/update` with the extra form field `skipValidation=1`; the partition
  table is unchanged so OTA works. Then restore
  `glorb/factory-0.14.4-GLORB.1.3/{presets,ledmap}.json`. The `cfg.json`
  there is a scrubbed reference (SSID, mDNS name, coordinates, Hue IP and
  remote MAC emptied) — set those in the UI, do not upload it verbatim.

If you have two lamps, keep one on factory and run `make verify
REF=<factory> TARGET=<ported>`: it recalls every preset on both lamps at
full brightness and compares their current estimates (the output stage —
mapping, gamma, brightness, ABL — which liveview cannot see). About 15 min
(70 s per preset); a FAIL row is worth an issue with the whole table. Motion
and colour are checked with `compare`, not by the gate. Both lamps end on
preset 4. With one lamp, `wledlab.py analyse` on your captures against the
numbers in "GLORB facts" is the next best thing. Either way, tell us what
you found (see `CONTRIBUTING.md`).

Factory `presets.json`/`ledmap.json` are SNRGY's data, redistributed here so
owners can restore their lamps; the tooling is MIT (see `LICENSE`).

## Layout

- `wledlab.py` — stdlib-only CLI (`--help` documents every subcommand).
- `glorb/factory-0.14.4-GLORB.1.3/` — factory `cfg.json`, `presets.json`,
  `ledmap.json` as shipped in SNRGY's littlefs image (rollback set).
- `glorb/wled16-port/` — what runs on a GLORB under stock WLED 16.0.1:
  byte-exact `ledmap.json`, ported `presets.json`, custom palettes generated
  by `glorb/mkpalettes.py` from the factory `palx.json`, and the cfg keys that
  must be posted to `/json/cfg`.

## The process (any lamp, any effect)

1. **Fingerprint the reference** while it still runs the old firmware:
   `wledlab.py capture --host REF --seconds 120 --out captures/ref-p1.json`
   then `wledlab.py analyse captures/ref-p1.json`. Read `raster_r2` first:
   if `rowmajor` ≈ 0.9 or above the effect is a 1D algorithm run over the
   raster (WLED "Pixels" mapping, `m12=0`); a 2D plane wave scores lower.
   Wavelength / stripes-per-turn / drift / hue range / hue cycle are the
   target numbers (`wledlab.py --help` explains each metric; on short rows
   trust `stripe_period` over `wavelength`; `activity` is the speed measure
   for plasma and sparkle effects — presets 4/5 read 1.00/1.02 once their
   motion matched, Hiphotic was tuned on it). `--width`/
   `--height` go before the subcommand for lamps that are not 20×6.
2. **Pick the stock effect and parameters** from the numbers and the effect
   metadata (`/json/fxdata`): `ix` on Colorwaves is the _spatial_ hue
   gradient, `c3` is 5-bit, 1D-on-2D orientation is `m12` + `tp`/`rY`
   (`rev` flips the _virtual_ axis, which after transpose is physical Y).
3. **Install byte-exact** with `wledlab.py install --host TARGET --ledmap …
--presets … --palette … [--reboot]` (refuses ledmaps without `"map":[`,
   reloads the map via `{"ledmap":0}`, checks `cpalcount` against the
   uploaded palettes, then applies every preset and compares all segments).
   Palettes reload on upload and presets are read per apply, so a reboot is
   optional. WLED 16 validates the ledmap as JSON and then scans the raw
   bytes for `"map":[`; keep `width`/`height` before `map` (16.0.0 read
   trailing keys as map entries).
4. **Prove the physical mapping**: `wledlab.py check-ledmap --ref REF
--target TARGET` — ratio 1.0 means the same number of physical LEDs are
   written; 1.5 on a GLORB means the ledmap was ignored (identity mapping).
   Liveview cannot see this; it shows logical cells on both firmwares. This
   is a smoke test (any 80-LED map passes); the correctness argument is that
   the `map` array is byte-identical to the factory file and both firmwares
   map `-1` to "unwritten".
5. **Compare** with `wledlab.py compare --ref REF --target TARGET --preset N
--seconds 120` — simultaneous windows, long enough to average WLED's
   `beatsin88` speed modulation (up to 104 s periods).
6. **Calibrate speed** with `wledlab.py calibrate-speed --ref REF --target
TARGET --preset N --seconds 120 --presets-file glorb/wled16-port/presets.json`
   — iterates `sx` on the target until stripe drift matches (rate ∝ 10+sx on
   frame-bound effects like Colorwaves; time-based ones such as Running are
   linear in `sx`). Then `install --presets …`. Frame-bound rates depend on
   the lamp's FPS: calibrate with the same clients attached as in normal use
   (the WS liveview itself costs frames) and note `info.leds.fps`.
7. **Output stage** (invisible to liveview): 0.14 gamma-corrects input
   colours only, 16 gamma-corrects every rendered pixel → for palette
   effects set `light.gc = {bri:1,col:1,val:1}` on 16 (all three keys — a
   partial write defaults `col` back to `val`). With gamma off, 16's
   built-in palettes are wrong too: they are stored re-encoded for the 2.2
   gamma (`palettes.cpp` header), so every ported preset uses a custom
   palette carrying the 0.14 stop values (`mkpalettes.py`, mode `plain`).
   For a true 1:1 test push the same frame to both lamps with `push-frame`
   (0.14 needs `--ref-input-gamma`).

Capture caveats: both firmwares serve the binary WS liveview (0.14 at ~15 Hz,
16 at ~25 Hz), which is what `capture` uses; the `lit` cell set is the union
over all frames. `check-ledmap`, `calibrate-speed` and `compare --preset`
write state to the lamps (white fill, `sx`, preset recall).

## Checks (each one exists because we got it wrong once)

| Rule                                                                                                                                                                        | Enforced by                                          |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Never claim "by construction" — the fork's `g`-flagged effects are modified algorithms; same palette ≠ same output                                                          | `verify`: current ratio + structural criteria        |
| Custom palettes: ≤18 stops, first index 0, last 255, committed file = generator output                                                                                      | `make lint` → `mkpalettes.py --check`                |
| Ledmap: exact bytes `"map":[`, valid JSON, `width`/`height` before `map`, `map` array byte-identical to factory                                                             | `make lint`, `install` refuses, `check-ledmap` ratio |
| Every uploaded file is read back byte-exact; every preset is applied and all segments compared (`bm`, `o1`, `col`, `bri` included); `cpalcount` covers every custom ID used | `install`                                            |
| Before a current-estimate read, drop every segment but 0 (a leftover multiply layer halves the fill)                                                                        | `check-ledmap`                                       |
| Liveview is logical and pre-output-stage: mapping, gamma, `bri` and ABL are only visible in `leds.pwr`                                                                      | `verify`, `check-ledmap`                             |
| Both lamps captured simultaneously over the same WS liveview path; `lit` = union over frames; hue/saturation only from cells bright enough to have a hue                    | `compare`, `analyse`                                 |
| Brightness is matched on `leds.pwr` above the ~120 mA standby floor (1 mA/LED), not on liveview means                                                                       | `verify`                                             |

Change anything → `make verify` (lint + acceptance against both lamps, 70 s per preset).
A red gate is the finding; do not tune by eye on top of it.

## Composites: how the fork's "one colour that cycles" effects were rebuilt

The fork's Running, Hiphotic and Tartan render a _uniform_ colour that
ping-pongs through the palette (index 0→255→0, ~35 s) on top of a brightness
pattern. Stock WLED colours those effects by position instead. WLED 16 segment
blend modes make the factory look composable without firmware code:

- segment 0: the stock effect as a brightness pattern — palette 3 "* Colors
  1&2" with a grey→white pair for Hiphotic (floor 130, scales `sx`/`ix` 32,
  speed `c3 31`), plain white for Running and for Tartan's lines (the fork
  draws every line at full brightness; a gradient capped the peaks at 0.83×).
  Stock Hiphotic adds a raw time term to its index (`+a`): at `c3 12` it
  cycled every 1.8 s — `activity` matched the fork and the eye saw shimmer;
  the variance share above 1 Hz was 6× (Tertiary) and 65× (Fire) the fork's.
  `c3` is the only speed knob and WLED 16 stores it in 5 bits, so 31 is the
  slowest (4.1 s); the scales and floor were then fitted on the lamp to the
  fork's spectrum, global-vs-spatial ratio and spatial activity (`c3 54–120`
  candidates all ran at 31 — read parameters back before trusting a search);
- segment 1 on the same cells: effect `Palette` (65), `Animate Shift` on,
  blend mode `bm 6` (multiply) — the colour. Size `ix` sets the spatial hue
  variation: 1 for Running/Tartan (the fork is uniform there), 13/24 for
  Hiphotic (the fork shows ~7° across the raster). `sx` sets the cycle:
  `sx 8` ≈ 33 s for Running 4, Hiphotic and Tartan (fork ~30–35 s), `sx 24`
  ≈ 16 s for Running 5 (fork 18 s — its Running cycle follows the effect
  speed);
- the colour layer's palette is the factory palette **mirrored** (palette +
  reverse), so the Palette effect's sawtooth becomes the fork's triangle.

Every single-segment preset carries `{"id":1,"stop":0}` so recalling it
removes the colour layer. Presets 1/3 (Colorwaves) stay single-segment: the
stock algorithm already cycles hue, it only needed the 0–127 compressed palette.

## GLORB facts worth not rediscovering

- 80 face LEDs on a 20×6 raster; physical pixels 0/21/62 are non-face and
  deliberately unmapped; cfg total stays 120.
- Factory Colorwaves/Running are the stock 1D algorithms over the row-major
  raster. The "rotating 45° axis / bubbling" is the 20-cell helix: tilt = 20
  mod wavelength, wavelength breathes 6.4↔10.2 on the 75.7 s `beatsin88(203)`
  clock. The animation never loops in practice (five free-running clocks).
- Stock Colorwaves sweeps palette index 0–127 only; the fork sweeps 0–255 →
  `palette0/1.json` are Analogous/Sunset mirrored into 0–127/128–255 (IDs
  200/199); `palette2..6.json` and `palette11.json` are Atlantica/Analogous/
  Tertiary/Fire/Fairy Reaf/Analogous mirrored for the colour layers (IDs
  198..194, 189); `palette7/8.json` are the plain 0.14 Analogous/Fire stops
  for Frizzles (IDs 193/192); `palette9/10.json` are the first 220/255 and
  40/255 of Tertiary/Sunset for Black Hole (IDs 191/190).
- WLED keeps every palette as 16 slots and blends linearly between them. A
  0–127 sweep therefore sees 8 slots, and FastLED's loader rounds packed
  stops into neighbouring slots — up to 34° hue error on Analogous with the
  factory stops simply packed. The mirrored palettes are instead 17 stops on
  exact slot indices whose colours are a least-squares fit of the fork's own
  16-slot trajectory, computed with the firmware's integer arithmetic and per
  effect: Colorwaves reads with `LINEARBLEND_NOWRAP` (WLED 16 remaps the
  index by 240/256), the Palette effect with `LINEARBLEND` (no remap).
  The fit weights the sweep's turning points so the anchor colours (pure red,
  pure blue) land where the fork's do. A layer is fitted over the index span
  the fork actually visits (Fire: 112–224, dark red to orange — the hue
  census shows 88 % red, 12 % orange and no yellow-white; a flat dwell over
  that span predicts 88 %).
- Dwell: the Palette effect shifts its index linearly, so every palette
  region gets equal time. The fork's Hiphotic and Tartan drive the index with
  a sine and linger at both palette ends (measured share per eighth of the
  palette on the factory lamp: ends 17–29 %, middle 8–12 %; Running is flat).
  Those layers are fitted over the arcsine-warped sweep (`mkpalettes.py`
  dwell `sine`), which is why Tartan – Analogous has its own layer palette
  (189) next to Running – Analogous (197). `mkpalettes.py --report` prints
  the residual: Analogous 11°, Sunset 11°, Fire 7°, Fairy Reaf 5°, worst
  Tertiary 22° at its sharp transitions — the 8-slot limit itself.
- Black Hole: the fork's Intensity slider limits the palette range its stars
  use (preset 11: 40/255 of Sunset — red to orange, hue never above 20°;
  preset 10: 220/255 of Tertiary); its other sliders keep the stock
  positions (fade `sx`, outer Y `ix`, inner X `c2` — trail length matched at
  19 vs 20 lit cells). Stock Black Hole indexes the whole palette (`i*32`,
  `255-i*64`), so preset 11 uses the first 40/255 of Sunset stretched to
  0–255 (`mkpalettes.py` mode `plain` with a range). The fork's stars also
  mix colours within a frame (65° spread) and drift through the palette
  together — no fixed star index reproduces that, so preset 10 is a
  composite: white stars (`o1` Solid, palette 0) × a Palette colour layer
  over Tertiary 0–220 with sine dwell (ID 191).
- Tartan adds its two line sets, so where lines cross the fork shows
  clip(2·colour) — (101,0,158) becomes (202,0,255); 39 % of its lit pixels
  are clipped. The port's multiply composite caps every pixel at the colour,
  so the Tartan – Analogous layer palette is boosted ×1.4 and clipped
  (k 2 measured +30 % per-hue brightness over the fork, 1.7 +20 %, 1.4 on
  it). Fairy Reaf is pastel: any boost clips channels and shifts hue (k 1.42
  moved 53 % of the time into cyan), so preset 12 stays unboosted.
- Residual in every mirrored layer: the port shows ~10 points more blue
  than the fork (Tertiary 31 % vs 20 %) with red matched. A half-strength
  dwell warp changes nothing, so it is the 8-slot chord from blue into cyan
  holding a blue hue longer than the fork's 16-slot path — only more slots
  would fix it, and the mirror needs them for the down sweep.
- Speed map, measured: fork 60 ↔ stock 4 (7.4 s per turn), fork 255 ↔ stock 12.
- Frizzles acceptance is peak brightness and lit-cell count against the fork
  (231 / ~25), not current: `verify` reports `peak_r`/`lit_r` per preset.
  Stock always draws 8 frizzles, so preset 7's reachable peak is bounded (see
  below) — that bound is a recorded limitation, not a knob to keep re-tuning.
- Frizzles: the fork sparkles to a per-frame peak of 231 with ~25 lit cells.
  A `bri` cap chosen for equal current (156) flattened the port to a peak of
  135 — current alone is the wrong target for sparkle effects. Fitted on
  peak, lit count, brightness histogram and current at once: preset 9 `bri
255`, blur `c1 80` (lit 23 vs 27, peak 168 vs 177, current 1.04); preset 7
  keeps blur 186 at `bri 200` — stock always draws 8 frizzles, so the port
  lights 41 cells to the fork's 25; the gate allows 1.13× the current, which
  buys a peak of ≈180 to the fork's 231 (`bri 220` reached it at 1.21×). The
  Smear option (`o1`) only adds bright cells (+40 % current).
- Running: fork cycles one colour over time; stock colours by position —
  hence the composite. Measured per preset, never scaled from another one:
  preset 4 `sx 43`/`ix 128` (8-cell wave, ~2.2 cells/s under liveview),
  preset 5 `sx 64`/`ix 144` (7 cells, 3.25 cells/s) — the fork's speed is
  not linear in its `sx`, and its colour cycle follows the effect speed
  (35 s at preset 4, 18 s at preset 5 → layer `sx 8` / `sx 24`). Hiphotic
  and Tartan cycle in ~30 s at every speed.
- Rollback: OTA `firmware_gma_83.bin` with form field `skipValidation=1`
  (16 rejects unsigned images otherwise); partition table is still factory.
  `ota.same-subnet=true` in the factory cfg blocks cross-VLAN OTA.
