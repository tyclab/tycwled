# fleet — the firmware our own lamps run

| Lamp            | IP          | Syslog host (Loki `host`)                                           | Hardware                                                             | Env              |
| --------------- | ----------- | ------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------- |
| Led Strip Couch | 10.27.4.58  | `wled-couch` (`um.Syslog.hostname`; its mDNS name is `wled-1271e8`) | ESP32, 4 MB flash, 300 LEDs on GPIO 2                                | `fleet_esp32`    |
| Moon            | 10.27.4.59  | `wled-moon`                                                         | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18                 | `fleet_esp32`    |
| GLORB           | 10.27.4.60  | `wled-glorb-links`                                                  | ESP32-S3, 8 MB                                                       | `fleet_glorb`    |
| GLORB           | 10.27.4.61  | `wled-glorb-rechts`                                                 | ESP32-S3, 8 MB                                                       | `fleet_glorb`    |
| Curtain Bench   | 10.27.4.221 | `tyccurtain`                                                        | Gledopto GL-C-618WL, ESP32, three 520-pixel outputs on GPIOs 16/12/4 | `fleet_gledopto` |
| WLED Spare      | 10.27.4.222 | `tycledspare`                                                       | DOMRAEM DOM-WLE-ADM, ESP32, two outputs on GPIOs 16/2                | `fleet_esp32`    |

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
Gledopto relay 18 (not inverted), PDM mic 32/15; DOMRAEM relay 12 (not inverted),
digital mic 26/5/21. Image hashes (build 2610050):

```text
35179a8e089edfccde25703b53e25f2748d36b54c00ec25fd9877e56d098380e  fleet_gledopto.bin
be0e2a5b532bc03f44e31bc22959a15418ce409b0c59e8fcc079f6a115b3a17b  fleet_esp32.bin
```

## Curtain

The Govee H70B5 curtain hangs as three panels of 20 vertical strings × 26 LEDs on the
GL-C-618WL. [`h70b5-gledopto.json`](../curtain/h70b5-gledopto.json) is its configuration
overlay, [`ledmap.json`](../curtain/ledmap.json) its 2D map, generated by
[`mkledmap.py`](../curtain/mkledmap.py); `make lint` fails when the committed map differs
from the generator output. `id.name` stays `Curtain Bench`, the device name Home Assistant
uses. The overlay leaves Ethernet, relay, microphone and Wi-Fi settings alone. Apply it with
the patched fleet build, which preserves unrelated settings on a partial configuration write:

```sh
python3 wledlab.py install --host 10.27.4.221 --cfg curtain/h70b5-gledopto.json
```

### Wiring

Each panel has its own data line from the controller, on the data conductor of the panel's
original 3-wire cable. The pixels carry factory addresses 0–519 in every panel, so panels on
a shared line repeat one picture. The cable's 36 V and GND conductors and each panel's
converter board stay as built; GND is shared between the controller and the panels. The
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

### Power

The global limit `hw.led.maxpwr` is 0, so each output limits itself: 4000 mA at 15 mA per
LED. WLED 16 applies a non-zero global limit instead of the per-output ones
(`BusManager::applyABL`), and a global limit that leaves less than 1 mA per LED (WLED's idle
estimate, 1560 mA here) after the ESP's reserve holds the curtain near black. The 15 mA per
LED is derived from the budget of the Govee 36 V 3 A (108 W) adapter for 1560 LEDs, not
measured. The three 4 A limits at 5 V cap the estimate at about 60 W, well under the adapter.
A reading of the adapter on a metering plug refines it.

The curtain boots off at brightness 16 and ignores incoming WLED sync. Realtime input (DDP
from the lightshow) runs at full brightness (`if.live.maxbri`) through the ledmap
(`if.live.rlm`).

### Ledmap

The ledmap is a 60 × 40 virtual grid in true proportions. The vertical LED pitch is 1.5 ×
the string pitch (1.4–1.6 measured from a straight-on photo; the strings hang closer together
than Govee spaced them, at their original heights). All three panels sit level in the map;
the middle panel hangs about half a row low at its left join and level at its right join. On
the integer grid the 1.5 pitch puts every panel's LED rows on grid rows 0, 2, 3, 5, 6, … 38,
so every third grid row is empty and a line one row thin can fall into a gap. Row 39 has no
LEDs either; it keeps the grid at the 60 × 40 of the lightshow's fixture. WLED reports a
60 × 40 matrix of 2400 cells, 1560 of them mapped, and an outline 16 strings wide and 16 rows
tall photographs square.

```sh
python3 wledlab.py install --host 10.27.4.221 --ledmap curtain/ledmap.json
```

`install` refuses a map without the exact bytes `"map":[`, uploads it as `/ledmap.json`, reads
it back byte for byte and reloads it. By hand:
`curl -F "data=@curtain/ledmap.json;filename=/ledmap.json" http://10.27.4.221/upload`, then
`POST /json/state` with `{"ledmap":0}`.

Without a `ledmap.json` on the controller the cfg matrix applies: three 20 × 26 panels at
x = 40 / 20 / 0 in output order, vertical, string 0 on the right, a 60 × 26 canvas without
the row pitch.

### Door

In ledmap columns (0 is the leftmost string seen from inside the room), the door frame spans
about 19.5–40.5: string 20 hangs in front of its left side, strings 39 and 40 in front of its
right side. The door glass spans about 20.5–38.5.
