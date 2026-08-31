# tycwled

Tools and data for putting the GLORB look back onto WLED 16, plus a way back to
the factory firmware. Made for our own two lamps, published so other GLORB
owners can do the same, check our numbers on their lamps, and improve on them.
Open an issue with what you see, or a pull request with what you changed.

## What this is now

The GLORB ships a closed fork of WLED 0.14.4. Its twelve factory presets do not
use a single stock effect — every one of them calls a custom effect the fork
added at fx 189–195 (Colorwaves, Running, Frizzles, Black Hole, Hiphotic,
Tartan). There is no source release.

Earlier revisions of this repo tried to approximate those effects with stock
WLED effects, segment composites and least-squares-fitted palettes. That was
the wrong foundation and it never converged. The six effects have since been
disassembled out of the public factory firmware image and reimplemented as a
WLED 16 usermod, and the factory palettes are shipped verbatim. The port is now
the same algorithms and the same colour data, not a lookalike.

Three pieces, all in this repo:

1. `glorb/usermod/glorb_fx/` — the six effects as a WLED 16 usermod. You build
   WLED yourself with it; there is no prebuilt binary here.
2. `glorb/wled16-port/` — `ledmap.json`, `presets.json`, six custom palettes and
   the cfg keys to post.
3. `glorb/factory-0.14.4-GLORB.1.3/` — the factory files, for rollback.

## GLORB owners: start here

You need a computer on the same network as the lamp (Python ≥ 3.10, `make`,
`curl`), the lamp's IP (router DHCP list, the WLED app, or
`http://wled-<xxxxxx>.local`), and PlatformIO to build the firmware. For
`verify` you also need a second GLORB still on factory firmware with its factory
presets — "ref" below is that lamp, "target" the ported one.

### 1. Build the firmware

```sh
git clone --depth 1 --branch v16.0.1 https://github.com/wled/WLED.git
ln -s "$PWD/glorb/usermod/glorb_fx" WLED/usermods/glorb_fx
cp glorb/usermod/glorb_fx/platformio_override.ini WLED/
cd WLED && pio run -e glorb_port
```

`audioreactive` must stay in `custom_usermods` — two of the fork's effects have
Sound Reactive branches, and the GLORB has a PDM microphone (`dmType 5`).

### 2. Flash it

Upload `.pio/build/glorb_port/firmware.bin` at `http://<lamp>/update`. If the
lamp answers "Access Denied — Client is not on local subnet", you are on a
different VLAN than the lamp: either flash from the lamp's own subnet or clear
`ota.same-subnet` first. OTA does not touch the filesystem, so presets,
palettes and the ledmap survive.

### 3. Find the effect IDs

The usermod registers with `addEffect(255, …)`, and WLED fills the reserved
gaps in its own mode table first — so the IDs are assigned at boot and are
**not** guaranteed to be the ones below. Read them off your lamp:

```sh
curl -s http://<lamp>/json/eff | python3 -c 'import json,sys; [print(i,n) for i,n in enumerate(json.load(sys.stdin))]'
```

On WLED 16.0.1 they land at 142 Colorwaves, 169 Running, 170 Frizzles,
171 Black Hole, 220 Hiphotic, 221 Tartan. The committed `presets.json` uses
those. If yours differ, remap the `fx` values before installing.

### 4. Install the files and the cfg

```sh
python3 wledlab.py install --host <lamp> \
  --ledmap glorb/wled16-port/ledmap.json \
  --presets glorb/wled16-port/presets.json \
  $(for n in 0 1 2 3 4 5; do echo --palette glorb/wled16-port/palette$n.json; done)
curl -X POST -H 'Content-Type: application/json' \
  --data @glorb/wled16-port/cfg-overrides.json http://<lamp>/json/cfg
```

`install` reads every file back byte-for-byte, then recalls each preset and
compares every segment field. The cfg post sets the factory gamma (2.8), FPS
and power cap.

### Rolling back to factory firmware

The images are in SNRGY's
[GLORB-WebInstaller](https://github.com/snrgy-studios/GLORB-WebInstaller)
(`bin/GLORB_0_14_4-1_3/firmware_gma_83.bin`). From WLED 16 upload it at
`/update` with the extra form field `skipValidation=1`; the partition table is
unchanged so OTA works. Then restore
`glorb/factory-0.14.4-GLORB.1.3/{presets,ledmap}.json`. The `cfg.json` there is
a scrubbed reference (SSID, mDNS name, coordinates, Hue IP and remote MAC
emptied) — set those in the UI, do not upload it verbatim.

Factory `presets.json`/`ledmap.json`/`palx.json` are SNRGY's data, redistributed
so owners can restore their lamps; the tooling is MIT (see `LICENSE`). The
factory firmware images are not redistributed here — fetch them from SNRGY.

## Verifying against a factory lamp

`make verify REF=<factory> TARGET=<ported>` recalls all twelve presets on both
lamps and captures them over the same window (100 s each, ~24 min), scoring
brightness distribution, hue, saturation, spatial structure, activity, peak and
lit-cell count. Both lamps end on preset 4. `wledlab.py rescore` re-runs the
same criteria offline over saved captures, so a tolerance change never costs
another 24 minutes on the lamps.

A red gate is the finding; do not tune by eye on top of it.

Two measurement rules the gate learned the hard way:

- **Current is the only instrument that sees the output stage.** Both firmwares
  serve the liveview *pre-gamma*, so two lamps can match on every captured
  metric and still look completely different to the eye. That is exactly what
  happened: with `gc` set to the factory's 2.8 the port's frames matched the
  fork's to within 2 % while it drew half the current, because WLED 16
  gamma-corrects every rendered pixel and 0.14.4 never does. So `verify` gates
  the current ratio, and a ratio far off 1.0 while the frame metrics agree means
  the two lamps disagree about gamma.
- **V alone cannot see a washed-out port.** Saturation is its own criterion.
  `rgbsum_r` is reported as an analogue of draw but never gated: at equal V and
  saturation a secondary hue sums twice a primary, so it moves with hue drift
  the hue axis already judges.

## Layout

- `wledlab.py` — stdlib-only CLI (`--help` documents every subcommand).
- `glorb/usermod/glorb_fx/` — the six decompiled effects as a WLED 16 usermod.
- `glorb/experiments/2026-08-31-reversing/` — how they were recovered from the
  firmware image: disassembly, notes, per-effect confidence.
- `glorb/factory-0.14.4-GLORB.1.3/` — factory `cfg.json`, `presets.json`,
  `ledmap.json`, `palx.json` (rollback set and source of truth for the port).
- `glorb/wled16-port/` — what to upload: byte-exact `ledmap.json`, translated
  `presets.json`, the six palettes `mkpalettes.py` emits, and `cfg-overrides.json`.

## GLORB facts worth not rediscovering

- 80 face LEDs on a 20×6 raster; physical pixels 0/21/62 are non-face and
  deliberately unmapped — the factory firmware never lights them either. The
  cfg bus total stays 120. `ledmap1.json` on some lamps is a linear 0..82 map
  for app/sACN streaming; it plays no part in effect rendering.
- **The built-in palettes are not the same palettes.** WLED regenerated most of
  its built-in gradients from cpt-city `.c3g` sources after 0.14 and stores them
  brighter. Analogous 18, red channel, is `3,23,67,142,255` in the fork and
  `38,86,139,196,255` in WLED 16 — roughly the fork's values with a 2.2 gamma
  removed. Of the six palettes the factory presets use, only Atlantica 51 is
  byte-identical, and Atlantica was the only preset that matched before this was
  found. So the port ships the factory stops verbatim as custom palettes
  200–195; WLED loads a custom palette through the same
  `loadDynamicGradientPalette` as a built-in gradient, so identical stops give
  an identical `CRGBPalette16`.
- **The port must run `light.gc` at 1.0, not the factory's 2.8.** WLED 0.14.4
  gamma-corrects user-set colours and custom palettes at load, never rendered
  effect output; WLED 16 gamma-corrects the whole frame in `show()`. So the
  factory's `gc 2.8` never touches a palette-driven preset on the fork, and
  copying it to the port applies a transform the reference lamp does not —
  which cost half the light output. Verified: setting `gc` to 1.0 moved the
  current ratios on presets 4/2/9 from 0.473/0.588/0.699 to 1.047/1.104/0.979.
- Every factory preset is single-segment at `bri 255`, `c3 16`, with `o1/o2/o3`
  off. Translating a preset means changing its `fx` and `pal` numbers and
  nothing else.
- The fork's effect metadata strings (slider names, the `2`/`v`/`g` flags) are
  in the firmware image as plain strings; the `g` flag is a UI badge, not
  something the render code reads.
- The GLORB usermod inside the fork is cloud/MQTT/app integration only — its
  vtable carries no `setup`/`loop`/`overlay` and it never writes pixels. It is
  not needed for visual parity.
- Both firmwares serve the binary WS liveview (0.14 at ~16 Hz, 16 at ~23 Hz),
  which is what `capture` uses, and both serve it pre-gamma. That the two are in
  the same space is checkable: gamma raises saturation sharply, and a matching
  preset measures S = 0.910 on the fork against S = 0.909 on the port.
- Rollback OTA needs form field `skipValidation=1` (16 rejects unsigned images
  otherwise); the partition table is still factory. `ota.same-subnet=true` in
  the factory cfg blocks cross-VLAN OTA.

## Checks (each one exists because we got it wrong once)

| Rule | Enforced by |
| --- | --- |
| Never claim "by construction" — same palette ID ≠ same colours, same effect name ≠ same algorithm | `verify` structural criteria |
| Custom palettes are the factory stops verbatim, ≤18 stops, first index 0, last 255, committed file = generator output | `make lint` → `mkpalettes.py --check`, `tests/test_palettes.py` |
| No preset may point at a built-in palette ID | `tests/test_palettes.py` |
| Ledmap: exact bytes `"map":[`, valid JSON, `width`/`height` before `map` | `make lint`, `install` refuses |
| Every uploaded file read back byte-exact; every preset applied and all segments compared | `install` |
| Current is not a cross-firmware criterion; brightness and saturation are measured from the frames | `verify` |
| Both lamps captured simultaneously over the same window; hue/saturation only from cells bright enough to have a hue | `verify`, `compare` |
