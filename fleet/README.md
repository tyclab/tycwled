# fleet — the firmware our own lamps run

| Lamp            | IP          | Syslog host (Loki `host`)                                           | Hardware                                                    | Env              |
| --------------- | ----------- | ------------------------------------------------------------------- | ----------------------------------------------------------- | ---------------- |
| Led Strip Couch | 10.27.4.58  | `wled-couch` (`um.Syslog.hostname`; its mDNS name is `wled-1271e8`) | ESP32, 4 MB flash, 300 LEDs on GPIO 2                       | `fleet_esp32`    |
| Moon            | 10.27.4.59  | `wled-moon`                                                         | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18        | `fleet_esp32`    |
| GLORB           | 10.27.4.60  | `wled-glorb-links`                                                  | ESP32-S3, 8 MB                                              | `fleet_glorb`    |
| GLORB           | 10.27.4.61  | `wled-glorb-rechts`                                                 | ESP32-S3, 8 MB                                              | `fleet_glorb`    |
| Curtain Bench   | 10.27.4.221 | `tyccurtain`                                                        | Gledopto GL-C-618WL, ESP32, one 520-pixel output on GPIO 16 | `fleet_gledopto` |
| WLED Spare      | 10.27.4.222 | `tycledspare`                                                       | DOMRAEM DOM-WLE-ADM, ESP32, two outputs on GPIOs 16/2       | `fleet_esp32`    |

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
  Use its existing Wi-Fi connection for the curtain rollout. The `ESP32_Ethernet`
  build supports Wi-Fi too; Ethernet cabling is optional. Preserve the Wi-Fi settings
  and use Wi-Fi MAC `70:4b:ca:48:91:c8` for the host reservation.
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

## Curtain bench

[`h70b5-gledopto-bench.json`](../curtain/h70b5-gledopto-bench.json) is applied to the
power-only GL-C-618WL after its fleet firmware upgrade. It starts
with **one** 520-pixel panel on GPIO 16: WS281x, RGB, 20 × 26, vertical,
non-serpentine, first pixel top left. It boots off at brightness 16, disables incoming
WLED sync, and retains the controller's factory 850 mA software limit for initial tests.
The controller reports a 20 × 26 matrix and is off at brightness 16 after reboot.
The overlay leaves Ethernet, relay, microphone and Wi-Fi settings alone. Use the patched fleet
build so partial configuration writes preserve unrelated settings.

This layout is a [Curtain Lights 2 community recipe](https://www.reddit.com/r/WLED/comments/1poi691/),
not yet verified on this H70B5. Before connecting anything, measure and identify the
panel's supply, ground and data connections; retain the factory power conversion and
never feed its 36 V adapter directly into the Gledopto (5–24 V input). Disconnect the
original data driver, share ground, and initially keep curtain power separate from
the controller's LED power terminals. Verify voltage before using any factory 5 V
rail to power the controller. Do not remove the reported end-of-string resistor until
its function and the signal fault are established on this hardware.

Confirm the first and last pixels, colour order and all 520 addresses before expanding
to GPIOs 16 / 12 / 4, three 520-pixel outputs and a 60 × 26 canvas. Size the final
power limit from the verified power path and load; 850 mA is only a conservative
single-panel bench setting, not a useful three-panel limit. Then reserve a fleet
hostname/address and add HA, the party watchdog and the lightshow's DDP output.
