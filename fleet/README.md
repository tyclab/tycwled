# fleet — the firmware our own lamps run

| Lamp            | IP         | Syslog host (Loki `host`)                                           | Hardware                                             | Env           |
| --------------- | ---------- | ------------------------------------------------------------------- | ---------------------------------------------------- | ------------- |
| Led Strip Couch | 10.27.4.58 | `wled-couch` (`um.Syslog.hostname`; its mDNS name is `wled-1271e8`) | ESP32, 4 MB flash, 300 LEDs on GPIO 2                | `fleet_esp32` |
| Moon            | 10.27.4.59 | `wled-moon`                                                         | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18 | `fleet_esp32` |
| GLORB           | 10.27.4.60 | `wled-glorb-links`                                                  | ESP32-S3, 8 MB                                       | `fleet_glorb` |
| GLORB           | 10.27.4.61 | `wled-glorb-rechts`                                                 | ESP32-S3, 8 MB                                       | `fleet_glorb` |

Both envs are WLED v16.0.1 plus [`syslog_events`](../usermods/syslog_events/),
sending to our collector at 10.27.2.41:1515.

- `fleet_esp32` is the stock `ESP32` release env (`esp32dev` with
  `audioreactive`) with the same release name. The Couch strip and the Moon
  **follow tycwled builds now, not stock updates.** A stock `ESP32` image
  still passes OTA validation and would silently drop the usermod. Update them
  by rebuilding here on the new WLED tag.
- `fleet_glorb` is `glorb_port` (glorb_fx, audioreactive, 16-bit PDM samples).

Pin, LED and mic settings live in each lamp's cfg.json, not in the build. A flash
changes only the firmware.

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
