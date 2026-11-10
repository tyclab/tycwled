# fleet — the firmware our own lamps run

| Lamp            | IP          | Syslog host (Loki `host`)         | Hardware                                                                                                                                        | Env              |
| --------------- | ----------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Led Strip Couch | 10.27.4.58  | `wled-couch` (also its mDNS name) | DOMRAEM DOM-WLE-ADM `04:b2:47:85:c8:14`, 300 LEDs on GPIO 16 (output 1)                                                                         | `fleet_esp32`    |
| Moon            | 10.27.4.59  | `wled-moon`                       | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18                                                                                            | `fleet_esp32`    |
| GLORB           | 10.27.4.60  | `wled-glorb-links`                | ESP32-S3, 8 MB                                                                                                                                  | `fleet_glorb`    |
| GLORB           | 10.27.4.61  | `wled-glorb-rechts`               | ESP32-S3, 8 MB                                                                                                                                  | `fleet_glorb`    |
| Curtain Bench   | 10.27.4.221 | `tyccurtain`                      | Gledopto GL-C-618WL (white) `70:4b:ca:5b:bd:d0`, three 520-pixel outputs on GPIOs 16/12/4                                                       | `fleet_gledopto` |
| Exoy            | 10.27.4.222 | `tycdodeca` (also its mDNS name)  | Gledopto GL-C-618WL (black) `70:4b:ca:48:91:c8`, both Exoy ONE lamps: 480 LEDs on GPIO 16 (window) and 480 on GPIO 12 (kitchen), a 60×16 matrix | `fleet_gledopto` |

All envs are WLED v16.0.1 plus [`syslog_events`](../usermods/syslog_events/),
sending to our collector at 10.27.2.41:1515, and [`tycstation_fx`](../usermods/tycstation_fx/),
the squid patterns as effects.

The overlays below rely on #5885's partial-config fix (`patches/5885-partial-config.patch`, in every
fleet build since 2610050), so apply them only to such a build. Lamps are not updated by rebuilding
here: a release and a flash are (see Release and Flash).

Rebuilding applies every `patches/*.patch` in name order to the pinned v16.0.1 source; a repeated
build accepts a patch already applied, and a mismatch stops the build. Remove a patch only when
the fleet's pinned release includes its fix.

[`patches/5885-partial-config.patch`](patches/5885-partial-config.patch) is the pending
[WLED #5885](https://github.com/wled/WLED/pull/5885) fix at
`adffde4b8bf03f8a506ab0477a42b977215c3a34`. Partial configuration writes must preserve
paired remotes, FPS, global auto-white mode and gamma.

[`patches/frozen-segment-reset.patch`](patches/frozen-segment-reset.patch) is named after what it
fixes: no upstream issue or PR covers it yet. Since WLED 16 (upstream `ee9ac947`,
[WLED #4658](https://github.com/wled/WLED/pull/4658)) `Segment::resetIfRequired()` blanks the
segment's pixels, and `WS2812FX::service()` runs it before the freeze check: a `/json/state` request
that changes the effect and sets pixels with `i` leaves the segment frozen and black, and an effect
change blanks a frozen segment; 0.15.3 kept the pixels. The patch defers the reset until the
segment is unfrozen and clears the pixel buffer a resize allocates. On the spare Gledopto, stock
build 2610050 lit 0 of 120 pixels after such a request, the patched build 2611092 all 120.

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
  Ethernet cabling is optional. Preserve the Wi-Fi settings and use the controller's Wi-Fi
  MAC for the host reservation (the curtain's is `70:4b:ca:5b:bd:d0` since 2026-10-07).
  Build it explicitly with `fleet/build.sh ../WLED-v16.0.1 fleet_gledopto`.

The DOMRAEM DOM-WLE-ADM uses `fleet_esp32`, retaining its `ESP32` release name and
its own microphone, relay and output configuration. As the couch controller its identity,
output, limits, remotes and central OTA access are in
[`overlays/couch-domraem.json`](overlays/couch-domraem.json).

The black GL-C-618WL drives both Exoy lamps. Its identity, boot preset, two outputs,
limits and 60×16 matrix are in [`overlays/exoy-gledopto.json`](overlays/exoy-gledopto.json),
read from the live controller.

Pin, LED and mic settings live in each lamp's cfg.json, not in the build. OTA retains
the filesystem, but a new WLED version can migrate its configuration schema on boot.

## Squid arm waves

`squid/` holds the TycStation squid's arm waves as animated GIFs for the Image effect, one
per lamp shape: `squid-arms-300x1.gif` (the couch strip as one 300-LED segment),
`squid-arms-20x6.gif` (a GLORB's raster) and `squid-arms-8x8.gif` (the Moon). Each matches
its segment's size, so WLED plays it unscaled. `curtain/squid/mkgifs.py` draws them together
with the curtain's loops. The Image effect plays on one segment per controller.

The files are drawn for a lamp that applies WLED's output gamma of 2.8, as the curtain, the
couch and the Moon do. The GLORBs run gamma 1.0 (`glorb/wled16-port/cfg-overrides.json`), so
`squid-arms-20x6.gif` holds the values that table gives the other lamps: every lamp then puts
the same values on the wire. A lamp whose gamma setting changes needs its file regenerated.

## TycStation palette

`tycstation/` holds the mark's gradient as a WLED custom palette, blue to violet to red and
back to blue, so any stock effect can run in the brand colours: `palette0.json` (ID 200, "Custom
0" in Home Assistant) for the curtain, the couch and the Moon, `glorb/palette6.json` (ID 194,
"Custom 6") for the GLORBs, after the port's six palettes and encoded for their output gamma of
1.0. `tycstation/mkpalette.py` writes both; `make check-palettes` checks them.

## TycStation effects

[`tycstation_fx`](../usermods/tycstation_fx/) runs the squid's patterns as code: Squid Arms
(the arm waves above), Squid Skin (the curtain's chromatophore cells) and Squid Plankton (the
deep-sea loop's water), on any segment, with Speed, a Sound slider for AudioReactive's volume
and one size slider each. It also registers the TycStation palette as usermod palette 255,
encoded for each lamp's gamma setting at runtime. WLED assigns the effect IDs at boot (142,
169 and 170 on `fleet_esp32` and `fleet_gledopto` and 222 to 224 on `fleet_glorb`, by the
v16.0.1 effect table), so presets name them. The squid figure stays a GIF.

No lamp runs a build with it yet. Once the lamps run it, the file palettes in `tycstation/`
(`palette0.json`, `glorb/palette6.json`, the files `mkpalette.py` writes and their
`check-palettes` step) are redundant and must be removed in that change; the usermod's tests
compare its stops with them and move with them.

## Build

```sh
git clone --depth 1 --branch v16.0.1 https://github.com/wled/WLED.git ../WLED-v16.0.1
nix shell nixpkgs#platformio-core nixpkgs#nodejs --command fleet/build.sh ../WLED-v16.0.1
```

Keep this checkout apart from any WLED clone used for upstream work: build.sh refuses
anything but the exact tag.

This produces `fleet/out/{fleet_esp32,fleet_glorb}.{bin,elf}`. It is untracked. Keep the ELF of whatever is on the
lamps: it decodes their crash lines. `WLED_VID=<vid>` rebuilds a given stamp.

## Release

The lamps run released builds. A tag `fleet-YYYYMMDD-<short sha>` on a commit of main makes
[`fleet-release.yml`](../.github/workflows/fleet-release.yml) build all three envs with `build.sh`
and publish `fleet_esp32`, `fleet_gledopto` and `fleet_glorb` as `.bin` and `.elf` with a
`SHA256SUMS` as that tag's release. The build stamp (`vid`) is the tag's date and the count of that day's earlier releases, `YYMMDDn`,
so every release has its own stamp.
The workflow refuses a tag whose short sha is not the tagged commit or whose commit is not on main.
Pull requests and main pushes that change the build only build it. A build takes about 2.5 minutes
from a cold cache and about 1 minute warm. Two builds of the same source are not byte-identical, so
the release's `SHA256SUMS` name the bytes that are flashed.

```sh
tag=fleet-$(date +%Y%m%d)-$(git rev-parse --short=7 origin/main)
git tag "$tag" origin/main && git push origin "$tag"
```

## Flash

tycpve's on-demand `wled:flash` job flashes a release: it pins the release's images by sha256,
reads only the selected lamp's PIN and OTA password from OpenBao inside CI, and runs the
`flash` below (and on a GLORB the effect-ID check). No credential is needed on a PC. Done by hand,
one lamp at a time, and stop if one does not come back:

```sh
python3 wledlab.py flash --host 10.27.4.58 --firmware fleet/out/fleet_esp32.bin --release ESP32 --credentials-file /path/to/private-couch.json
python3 wledlab.py flash --host 10.27.4.60 --firmware fleet/out/fleet_glorb.bin --release ESP32-S3_8MB_qspi --credentials-file /path/to/private-glorb-left.json
```

`flash` snapshots `/json/info`, `/json/cfg` and `presets.json` under
`captures/flash/`, uploads to `/update`, waits for the reboot, then fails unless
cfg is unchanged apart from `vid` and a new usermod block, and presets are
byte-identical. Pass `--skip-validation` only when the release name changes on
purpose. On a GLORB, also run `install --effects glorb/wled16-port/effects.json`
afterwards with the same `--credentials-file`: the port presets need the glorb_fx IDs.

The fleet's settings PIN and OTA password are stored per device in OpenBao's
`secret/hatyc/creds` by tycpve's `bao:seed-wled-security` job. The private JSON
file contains `pin` and `ota_password`; see
[protected fleet maintenance](../README.md#protected-fleet-maintenance).
The updater temporarily unlocks OTA, restores its protection before checking
configuration, and relocks settings even after a failed upload. If the device
cannot be reached to relock it, recover that device before continuing.

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

The Gledopto and the DOMRAEM, both spares at the time, passed this migration and retained
byte-identical presets. The Gledopto
was verified against its saved before/after snapshots after the initial strict check
identified the capacity/default/runtime-format differences above. Hardware preserved:
Gledopto relay 18 and DOMRAEM relay 12, both cfg `rev: false`, which is the ticked Invert box
(WLED loads the key as the opposite of its relay mode; the GL-C-618WL manual prescribes Invert);
Gledopto PDM mic 32/15, DOMRAEM digital mic 26/5/21. Image hashes (build 2610050; the second Gledopto
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
the MAC. The black GL-C-618WL became the spare, with four 30-pixel outputs; switching 2D off
(`/settings/2D`, which drops the matrix) and deleting `ledmap.json` and `tycstation.gif` were
manual steps an overlay cannot express. Since 2026-11-09 it drives the Exoy lamps.
The DOMRAEM became the couch controller: [`overlays/couch-domraem.json`](overlays/couch-domraem.json)
holds every key the swap changed on it (identity, output 1 on GPIO 16, limits, ESP-NOW remotes,
node and sync settings, AudioReactive options), checked key by key against the live controller;
[`overlays/couch-presets.json`](overlays/couch-presets.json) are the couch's presets. The strip
moved from the old ESP32's GPIO 2 to the DOMRAEM's output 1. The reservations moved with the roles in tycnetwork !998. Full
pre-swap file sets of all four controllers are kept outside git in
`~/.local/share/tycwled/backups/2026-10-07-swap/` (they hold no Wi-Fi secrets; WLED keeps
those in `wsec.json`, which it never serves). The old couch ESP32 (`08:d1:f9:12:71:e8`) is
retired for good: on the couch strip and its 8 A supply it logged a brownout reset 6 s into white at
brightness 128 (and ten brownout resets on 6 and 7 October), while the DOMRAEM on the same strip
and supply did not reset during white stepped up to brightness 255 nor during a 30 s strobe at 255
(uptime polled every 2 s). The DOMRAEM is the permanent couch controller. Its per-LED current is
the 5 V model (`ledma` 55) with an 8 A global limit, the supply's rating: WLED estimates full white
at 16.8 A and scales it to about 120/255. Operator, 2026-10-07: at this setting the far third no
longer shows the yellow-green cast it had at full white under the WS2815 model (`ledma` 255,
12 mA per LED, where the cap never engaged), and raising the limit brings the cast back.

## Remote

Every lamp pairs the ESP-NOW remotes tycpve's `wled:remotes` declares; a lamp ignores any other
sender (until 2026-11-10 the second remote was unpaired and moved no lamp; `wledlab.py remotes`
shows the last sender a lamp heard). No lamp carries a `remote.json`, so WLED
16.0.1's own handler runs (`remote.cpp`): number button N calls preset N, and on, off, night and
the brightness buttons act on the whole lamp. A lamp with no preset in that slot stays as it is
and logs `error: code=12 (preset does not exist)`. The fallback effects named in `remote.cpp`
are never shown: `handlePresets()` ends in `stateUpdated()`, which reads the effect back from
the segment before anything applies it (`presets.cpp`, `led.cpp`; on 2026-11-10 the couch's
segment did not change on the buttons it has no preset for).

A `remote.json` that sends `{"ps": N}` for those buttons gains nothing and loses two things the
stock handler does: the JSON path skips a preset that is already current (`json.cpp`), and it
does not end the remote's night mode, which then blocks the brightness buttons (`remote.cpp`).

Presets 1 to 7 are therefore the remote's looks on every lamp: a look saved into one of those
slots is on its button at once, and anything that is not a look (a boot layout, a test pattern)
belongs above 7. The couch's boot layout is preset 250 for that reason; in slot 2 it switched
the strip off from the remote (2026-11-10).

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
a shared line repeat one picture. The cable's 36 V and GND conductors and the three panels'
converter boards stay as built; GND is shared between the controller and the panels. The
middle panel's converter board failed in the full-white test (see Power) and was replaced with
a new board of the same kind, so the three panels are built identically (operator,
2026-11-02); the 5 V 8 A supply once planned in its place was never wired. The epoxy blob at
the end of the top string, a resistor on the data line, is cut off. The 36 V adapter never
connects to the Gledopto (5–24 V input).

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
the per-output limits stay well under that. The middle panel runs on a new board of the same
kind, and the limits are uniform across the three outputs.

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
