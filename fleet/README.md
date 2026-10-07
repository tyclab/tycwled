# fleet — the firmware our own lamps run

| Lamp            | IP          | Syslog host (Loki `host`)         | Hardware                                                                                  | Env              |
| --------------- | ----------- | --------------------------------- | ----------------------------------------------------------------------------------------- | ---------------- |
| Led Strip Couch | 10.27.4.58  | `wled-couch` (also its mDNS name) | DOMRAEM DOM-WLE-ADM `04:b2:47:85:c8:14`, 300 LEDs on GPIO 16 (output 1)                   | `fleet_esp32`    |
| Moon            | 10.27.4.59  | `wled-moon`                       | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18                                      | `fleet_esp32`    |
| GLORB           | 10.27.4.60  | `wled-glorb-links`                | ESP32-S3, 8 MB                                                                            | `fleet_glorb`    |
| GLORB           | 10.27.4.61  | `wled-glorb-rechts`               | ESP32-S3, 8 MB                                                                            | `fleet_glorb`    |
| Curtain Bench   | 10.27.4.221 | `tyccurtain`                      | Gledopto GL-C-618WL (white) `70:4b:ca:5b:bd:d0`, three 520-pixel outputs on GPIOs 16/12/4 | `fleet_gledopto` |
| WLED Spare      | 10.27.4.222 | `tycledspare`                     | Gledopto GL-C-618WL (black) `70:4b:ca:48:91:c8`, four 30-pixel outputs on GPIOs 16/12/4/2 | `fleet_gledopto` |

All envs are WLED v16.0.1 plus [`syslog_events`](../usermods/syslog_events/),
sending to our collector at 10.27.2.41:1515.

The curtain and spare run build 2610050 with #5885. Older lamps are not automatically
updated by rebuilding here.

Rebuilding now also applies [`patches/5885-partial-config.patch`](patches/5885-partial-config.patch),
the pending [WLED #5885](https://github.com/wled/WLED/pull/5885) fix at
`adffde4b8bf03f8a506ab0477a42b977215c3a34`. Partial configuration writes must preserve
paired remotes, FPS, global auto-white mode and gamma. The patch applies to the pinned
v16.0.1 source; a repeated build accepts it already applied, and a mismatch stops the build.
Remove it only when the fleet's pinned release includes the fix.

- `fleet_esp32` is the stock `ESP32` release env (`esp32dev` with
  `audioreactive`) with the same release name. The Couch strip and the Moon
  **follow tycwled builds now, not stock updates.** A stock `ESP32` image
  still passes OTA validation and would silently drop the usermod. Update them
  by rebuilding here on the new WLED tag.
- `fleet_glorb` is `glorb_port` (glorb_fx, audioreactive, 16-bit PDM samples).
- `fleet_gledopto` is the stock `esp32_eth` environment with AudioReactive and syslog,
  retaining the `ESP32_Ethernet` release name for the GL-C-618WL. Its GPIOs, Ethernet
  type, relay polarity and microphone settings remain device configuration. Gledopto
  Ethernet support is already in v16.0.1; no vendor firmware overlay is needed.
  The curtain runs on Wi-Fi. The `ESP32_Ethernet` build supports Wi-Fi too;
  Ethernet cabling is optional. Preserve the Wi-Fi settings and use Wi-Fi MAC
  `70:4b:ca:48:91:c8` for the host reservation.
  Build it explicitly with `fleet/build.sh ../WLED fleet_gledopto`.

The DOMRAEM DOM-WLE-ADM uses `fleet_esp32`, retaining its `ESP32` release name and
its own microphone, relay and output configuration. Its fleet identity and central
OTA access are in [`domraem-spare.json`](domraem-spare.json).

Pin, LED and mic settings live in each lamp's cfg.json, not in the build. OTA retains
the filesystem, but a new WLED version can migrate its configuration schema on boot.

## Build

```sh
git clone --depth 1 --branch v16.0.1 https://github.com/wled/WLED.git ../WLED
nix shell nixpkgs#platformio-core nixpkgs#nodejs --command fleet/build.sh ../WLED
```

This produces `fleet/out/{fleet_esp32,fleet_glorb}.{bin,elf}`. It is untracked. Keep the ELF of whatever is on the
lamps: it decodes their crash lines. `WLED_VID=<vid>` rebuilds a given stamp.

## Flash

One lamp at a time, and stop if one does not come back:

```sh
python3 wledlab.py flash --host 10.27.4.58 --firmware fleet/out/fleet_esp32.bin --release ESP32
python3 wledlab.py flash --host 10.27.4.60 --firmware fleet/out/fleet_glorb.bin --release ESP32-S3_8MB_qspi
```

`flash` snapshots `/json/info`, `/json/cfg` and `presets.json` under
`captures/flash/`, uploads to `/update`, waits for the reboot, then fails unless
cfg is unchanged apart from `vid` and a new usermod block, and presets are
byte-identical. Pass `--skip-validation` only when the release name changes on
purpose. On a GLORB, also run `install --effects glorb/wled16-port/effects.json`
afterwards: the port presets need the glorb_fx IDs.

For the reviewed classic-ESP32 spare upgrades from 0.15.1/0.15.3 only, add
`--cfg-migration 0.15-to-16.0.1`. This predicts v16's configuration from the original
snapshot and still compares every resulting field. It checks source version, hardware,
release and the target version; configured timers or unreviewed LED types are refused
before upload. Pass `--mac` to verify the controller identity before upload; after a
reboot the MAC must always match. Snapshots are private files under `captures/flash/`.

The migration follows v16.0.1's `cfg.cpp`, `const.h`, `network.cpp` and `wled.cpp`:
remotes become a list; new BSSID pinning is empty; unused button slots disappear and
the reported button capacity becomes 32; obsolete global LED/transition fields
disappear; outputs gain RMT driver/text fields; DMX input gains unassigned pins; and
an unset Hue IP prefix follows the connected interface. OTA defaults to same-subnet
access. Neither GPIO changes nor lost microphone, Wi-Fi or preset settings are ignored.
The fleet config overlays then explicitly retain cross-subnet OTA access for updates
from the management network, matching the existing fleet.

Both spares passed this migration and retained byte-identical presets. The Gledopto
was verified against its saved before/after snapshots after the initial strict check
identified the capacity/default/runtime-format differences above. Hardware preserved:
Gledopto relay 18 with Invert ticked (cfg `rev: false` is that ticked box: WLED loads the key
as the opposite of its relay mode), PDM mic 32/15, as the GL-C-618WL manual prescribes;
DOMRAEM relay 12, digital mic 26/5/21. Image hashes (build 2610050; the second Gledopto
image is the 2026-10-07 rebuild at the same stamp, flashed to the white controller):

```text
35179a8e089edfccde25703b53e25f2748d36b54c00ec25fd9877e56d098380e  fleet_gledopto.bin (2026-10-05)
895bbaf45f50a8912f2c607661b5157cdcc9b50a8a8e03111f2f6dc94de91616  fleet_gledopto.bin (2026-10-07 rebuild)
be0e2a5b532bc03f44e31bc22959a15418ce409b0c59e8fcc079f6a115b3a17b  fleet_esp32.bin
```

### Controller swap, 2026-10-07

The white GL-C-618WL took over the curtain: flashed from stock 0.15.3 with
`wledlab.py flash --cfg-migration 0.15-to-16.0.1`, then the first controller's `/json/cfg`
(outputs, matrix, power limits, Ethernet off, live input, sync, OTA, syslog name), `ledmap.json`,
`presets.json`, `tycstation.gif` and `pftools.json` were installed byte-exact; the only keys that
differ from the black one afterwards are the MQTT client id and topic, which WLED derives from
the MAC. The black GL-C-618WL became the spare ([`overlays/spare-gledopto.json`](overlays/spare-gledopto.json):
neutral four-output layout, 2D off via `/settings/2D`, curtain files removed) and the DOMRAEM
became the couch controller ([`overlays/couch-domraem.json`](overlays/couch-domraem.json) with the
couch's presets, ESP-NOW remotes and node settings; the strip moves from the old ESP32's GPIO 2 to
the DOMRAEM's output 1, GPIO 16). The reservations moved with the roles in tycnetwork !998. Full
pre-swap file sets of all four controllers are kept outside git in
`~/.local/share/tycwled/backups/2026-10-07-swap/` (they hold no Wi-Fi secrets; WLED keeps
those in `wsec.json`, which it never serves). The old couch ESP32 (`08:d1:f9:12:71:e8`) is
retired for good: on the couch strip and its 8 A supply it reset with a brownout at half-brightness
white (and logged ten brownout resets on 6 and 7 October), while the DOMRAEM on the same strip and
supply held static white up to full brightness and a 30 s full-brightness strobe. The DOMRAEM is the
permanent couch controller, at a 6 A global limit. Its per-LED current is the WS2815 model the
couch always ran with (`ledma` 255, 12 mA per LED), so WLED's estimate tops out near 4 A at full
white and the 6 A cap does not engage.

## Curtain

The Govee H70B5 curtain hangs as three panels of 20 vertical strings × 26 LEDs on the
GL-C-618WL. [`h70b5-gledopto.json`](../curtain/h70b5-gledopto.json) is its configuration
overlay, [`ledmap.json`](../curtain/ledmap.json) its 2D map, generated by
[`mkledmap.py`](../curtain/mkledmap.py); `make lint` fails when the committed map differs
from the generator output. `id.name` stays `Curtain Bench`, the device name Home Assistant
uses. The overlay switches Ethernet off (see Memory) and leaves relay, microphone and Wi-Fi settings alone. Apply it with
the patched fleet build, which preserves unrelated settings on a partial configuration write:

```sh
python3 wledlab.py install --host 10.27.4.221 --cfg curtain/h70b5-gledopto.json
```

### Wiring

Each panel has its own data line from the controller, on the data conductor of the panel's
original 3-wire cable. The pixels carry factory addresses 0–519 in every panel, so panels on
a shared line repeat one picture. The cable's 36 V and GND conductors and the right and left
panels' converter boards stay as built; GND is shared between the controller and the panels.
The middle panel's converter board failed (see Power), so a 5 V 8 A supply takes its place:
the panel's 5 V and GND leads move from the board's pads 1 and 2 to the supply, the
controller GND link moves to the supply's −, and the board's 36 V lead leaves the Wagos. The
epoxy blob at the end of the top string, a resistor on the data line, is cut off. The 36 V
adapter never connects to the Gledopto (5–24 V input).

### Outputs and panel order

| Output | GPIO | LEDs      | Panel, seen from inside the room |
| ------ | ---- | --------- | -------------------------------- |
| 1      | 16   | 0–519     | right                            |
| 2      | 12   | 520–1039  | middle, over the balcony door    |
| 3      | 4    | 1040–1559 | left                             |

Every output is WS281x (type 22), RGB (order 1), 520 pixels. Each panel runs vertical, top
first, non-serpentine, with string 0 on the panel's right side, so the curtain is the mirror
image of the [Curtain Lights 2 community recipe](https://www.reddit.com/r/WLED/comments/1poi691/)'s
"first pixel top left". At each join the left panel's string 0 hangs next to the right
panel's string 19.

### Memory

Ethernet is off (`eth.type` 0): the curtain runs on Wi-Fi, and the idle Gledopto Ethernet
driver held about 23 KB of heap, which the 68 × 42 canvas, the Image effect's GIF decoder
(about 24 KB) and the sound-reactive 2D effects need; with it on, effects failed with
"effect RAM depleted" (syslog error code 8).

### Power

The global limit `hw.led.maxpwr` is 0, so each output limits itself: 2500 mA at 30 mA per
LED. WLED 16 applies a non-zero global limit instead of the per-output ones
(`BusManager::applyABL`), and a global limit that leaves less than 1 mA per LED (WLED's idle
estimate, 1560 mA here) after the ESP's reserve holds the curtain near black.

Measured on a metering plug: with 4000 mA per output at 15 mA per LED, full white drew about
118 W at the wall and tripped the Govee 36 V 3 A (108 W) adapter's protection, so the real
current is about twice that estimate. 30 mA per LED keeps WLED's estimate close to the real
draw, and three 2.5 A outputs at 5 V cap full white at about 38 W, under half the adapter.
The controller runs on its own USB supply, so an adapter trip does not reset it.

That test also killed the middle panel's Govee converter board (36 V to 5 V): the stock
boards are built for Govee's own brightness ceiling, about 39 W per panel at the wall, so
the per-output limits stay well under that for the two stock boards. The middle panel's
replacement supply (5 V 8 A) has headroom, but the limits stay uniform across the outputs.

The curtain boots off at brightness 16 and ignores incoming WLED sync. Realtime input (DDP
from the lightshow) runs at full brightness (`if.live.maxbri`) through the ledmap
(`if.live.rlm`).

### Geometry

On the floor plan the window front is 2.78 m: left pane ≈ 0.86 m, balcony door ≈ 1.10 m
frame to frame, right pane ≈ 0.82 m. The left panel extends ≈ 0.4 m past the window and the
right panel ≈ 0.25 m, both behind the sheers.

The string positions are measured from a straight-on photo with every 5th string and each
panel's last string lit (`LIT` in [`mkledmap.py`](../curtain/mkledmap.py), px at 4000 px
wide); the strings between are interpolated. String spacing relative to the door panel:

| Part                                   | Spacing                                            |
| -------------------------------------- | -------------------------------------------------- |
| left panel, outer half (strings 0–10)  | ≈ 1.5×, near Govee's 7.5 cm, behind the sheer      |
| left panel, inner half (strings 10–19) | ≈ 1.1×                                             |
| middle (door) panel (strings 20–39)    | 1.0×, ≈ 5.1 cm (the door is 1.10 m frame to frame) |
| right panel (strings 40–59)            | ≈ 1.05–1.1×                                        |
| panel joins (19–20, 39–40)             | ≈ 1.3×                                             |

The LED rows are 53 px apart in every panel, 1.66× the door-panel spacing (≈ 8.5 cm); the
string heights are as built.

### Ledmap

The ledmap is a 68 × 42 grid of square cells, one door-panel string spacing (32 px) each way,
so a shape square on the grid is square on the curtain. The strings take columns left to
right at their measured position, rounded, each at least one column past its neighbour. A
column stays empty where the rounded positions skip one: every second gap in the left panel's
outer half (1.4–1.6 spacings; columns 1, 4, 7, 10, 13), and where the wider spacing of the
left panel's inner half and the right panel adds up to a whole column (23, 48, 60). The
joins skip none. LED row r sits on grid row r × 53/32 rounded half up (0, 2, 3, 5, 7, 8, …
41), so 16 of the 42 rows are empty. All three panels sit level. No two empty columns and no
two empty rows are adjacent: content drawn with strokes at least 2 cells wide in both
directions always reaches LEDs, a line 1 cell thin can fall into a gap. WLED reports a
68 × 42 matrix of 2856 cells, 1560 of them mapped.

The lightshow's `Curtain` fixture is patched from WLED's own report (`POST /api/wled/add`
with `mode: "pixels"`), so it takes the grid size WLED reports: 68 × 42, 2856 cells.

```sh
python3 wledlab.py install --host 10.27.4.221 --ledmap curtain/ledmap.json
```

`install` refuses a map without the exact bytes `"map":[`, uploads it as `/ledmap.json`, reads
it back byte for byte and reloads it. By hand:
`curl -F "data=@curtain/ledmap.json;filename=/ledmap.json" http://10.27.4.221/upload`, then
`POST /json/state` with `{"ledmap":0}`.

Without a `ledmap.json` on the controller the cfg matrix applies: three 20 × 26 panels at
x = 40 / 20 / 0 in output order, vertical, string 0 on the right, a 60 × 26 canvas of
evenly spaced strings and rows.

### Door

In strings counted from the left (0–59, seen from inside the room), the door frame spans
about 19.5–40.5: string 20 hangs in front of its left side, strings 39 and 40 in front of its
right side. The door glass spans about 20.5–38.5. In ledmap columns string 20 sits on column
26 and strings 39 and 40 on columns 45 and 46; the door panel's strings take one column each,
26–45.

### Logo

[`tycstation.gif`](../curtain/tycstation.gif) is the TycStation Krake mark (the site's
`favicon.svg` without its tile), 46 × 40 pixels placed at x 13, y 1 of a 68 × 42 frame, so it
sits centred on the door in the ledmap grid. WLED's Image effect (fx 53) draws the GIF named
by its segment, so the segment is named `tycstation.gif`;
[`presets.json`](../curtain/presets.json) keeps that as preset 1 "TycStation", which Home
Assistant's Evening look "TycStation" recalls. Both files upload like the ledmap
(`curl -F "data=@curtain/tycstation.gif;filename=/tycstation.gif" http://<host>/upload`,
the same for `/presets.json`). Rebuild the GIF with the tile removed from the SVG, then
`rsvg-convert -w 840 -h 840 -b black krake.svg -o krake.png` and
`magick krake.png -trim +repage -filter Box -resize 46x40! -modulate 100,140 -level 0%,80% m.png`,
`magick -size 68x42 xc:black m.png -geometry +13+1 -composite -strip tycstation.gif`.
