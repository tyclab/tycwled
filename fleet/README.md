# fleet — the firmware our own lamps run

| Lamp            | IP          | Syslog host (Loki `host`)              | Hardware                                                                                                         | Env              |
| --------------- | ----------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------- |
| TycCouch        | 10.27.4.58  | `wled-couch` (also its mDNS name)      | DOMRAEM DOM-WLE-ADM `04:b2:47:85:c8:14`, 300 LEDs on GPIO 16 (output 1)                                          | `fleet_esp32`    |
| TycMoon         | 10.27.4.59  | `wled-moon`                            | ESP32, 8 MB flash in the 4 MB layout, 8×8 on GPIO 18                                                             | `fleet_esp32`    |
| TycGlorbLinks   | 10.27.4.60  | `wled-glorb-links`                     | ESP32-S3, 8 MB                                                                                                   | `fleet_glorb`    |
| TycGlorbRechts  | 10.27.4.61  | `wled-glorb-rechts`                    | ESP32-S3, 8 MB                                                                                                   | `fleet_glorb`    |
| TycCurtain      | 10.27.4.221 | `tyccurtain`                           | Gledopto GL-C-618WL (white) `70:4b:ca:5b:bd:d0`, three 520-pixel outputs on GPIOs 16/4/12                        | `fleet_gledopto` |
| TycDodecaLinks  | 10.27.4.225 | `tycdodecalinks` (also its mDNS name)  | DOMRAEM DOM-WLE-A `70:4b:ca:8f:9c:b4`, the left Exoy ONE lamp (kitchen end): 480 LEDs on GPIO 16, a 30×16 matrix | `exoy_domraem`   |
| TycDodecaRechts | 10.27.4.226 | `tycdodecarechts` (also its mDNS name) | DOMRAEM DOM-WLE-A `70:4b:ca:8f:a5:a0`, the right Exoy ONE lamp (window end): 480 LEDs on GPIO 16, a 30×16 matrix | `exoy_domraem`   |

All envs are WLED v16.0.1 plus [`syslog_events`](../usermods/syslog_events/),
sending to our collector at 10.27.2.41:1515, and [`tycstation_fx`](../usermods/tycstation_fx/),
the squid patterns as effects.

The Lamp column is each controller's `id.name`, the name the WLED app shows (TycStation names since
2026-11-17). Its overlay carries it: the Moon and the GLORBs have overlays that hold only that name,
[`overlays/moon.json`](overlays/moon.json), [`overlays/glorb-links.json`](overlays/glorb-links.json)
and [`overlays/glorb-rechts.json`](overlays/glorb-rechts.json). Home Assistant and the lightshow reach
the controllers by host, so a name leaves hosts, mDNS names and Home Assistant entity ids alone.

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
segment is unfrozen and clears the pixel buffer a resize allocates. On the black GL-C-618WL, then
the spare, stock build 2610050 lit 0 of 120 pixels after such a request, the patched build 2611092
all 120.

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
[`overlays/couch-domraem.json`](overlays/couch-domraem.json). It receives no WLED UDP sync
(`if.sync.recv`): sync stays off where the lightshow does not need it (operator, 2026-11-06, when
it was switched off on the lamps). Its microphone is the Exoy lamps' sound source: the overlay
sends AudioReactive's sound sync (operator, 2026-11-18: "use sound sharing").

Each Exoy lamp has its own DOMRAEM DOM-WLE-A since 2026-11-18 (operator: one controller per
dodecahedron): TycDodecaLinks drives the left lamp at the kitchen end, TycDodecaRechts the right
lamp at the window end; the data wire is on GPIO 16. Their identity, boot preset, the one output,
its limit, the 30×16 matrix (one vertical panel, top start, not serpentine: row y is LED y of an
edge), gamma 2.8, forced full brightness for a live stream, no brightness from WLED sync
(`if.sync.recv.bri` false, see Remote) and AudioReactive are in
[`overlays/exoy-links-domraem.json`](overlays/exoy-links-domraem.json) and
[`overlays/exoy-rechts-domraem.json`](overlays/exoy-rechts-domraem.json). The DOM-WLE-A has no
microphone (operator, 2026-11-18; with the PDM setting on 26/21 that both came with, AudioReactive's
raw volume was 0 in 1,440 of 1,440 effect calls on TycDodecaRechts while the couch's microphone read
peaks). Both lamps take their sound from the couch: its overlay sends AudioReactive's UDP sound sync
(`sync.mode` 1, port 11988) and theirs receive it (`sync.mode` 2), so both get the same level. A
sender keeps processing sound while a live stream drives its own LEDs. The output is limited to
6000 mA at 55 mA per LED (operator, 2026-11-18: "set limit back to 6A"; 6500 mA each while one
black GL-C-618WL drove both lamps from one 5 V 12 A supply). The Exoy engine renders each scene
at its own frame period (`um.Exoy.period_us` 0, for image vid 2611181 and later; an older image
reads 0 as 11 ms): the unchanged original firmware's mean frame time in that scene in the emulator,
18.4 to 19.9 ms for 67 scenes, 22.5 ms for Rhythm Run and Gloze and 16.0 ms for the static Custom
Hue (tyclab/tycExoyWled `wled/scene-periods.tsv`; the emulator's CPU speed is not calibrated against
the chip, and the image's earlier single 16 ms was never measured). WLED shows a frame once per
frame time, 1000 / FPS in whole ms, on its own timer. From image vid 2611190 the Exoy usermod asks
WLED for a frame when the lamp's next one is due, as long as WLED's frame time is no shorter than
the scene's period, so that timer never shows a frame in between: both lamps run at 40 FPS (25 ms,
above the longest period, 22.5 ms). The overlay is for vid 2611190 and later: an older image at
40 FPS is called by the timer alone and shows 40 of the engine's 44 to 62 frames a second. Until
2026-11-19 both ran at 55 FPS (18 ms, below every moving scene's period), where WLED showed 54 to
55 frames a second whatever the scene's own rate. Each boots off (operator, 2026-11-19, on a
lamp lit after a power cut: "if we have power outage this happens and this an antipatern") with
its preset 250 loaded: the ten stock looks of "Exoy calm cycle" (20) at five minutes each, without
power. It stays dark until someone switches it on and then shows the first of them, not one plain
colour (operator, 2026-11-17). No preset sets a brightness (see Remote), so a lamp switched on
after power-on shows its `def.bri` (128) until someone sets another. Their image `exoy_domraem` (`fleet_esp32` plus the 70 Exoy effects) and
their presets come from tyclab/tycExoyWled, not from this repository.

Pin, LED and mic settings live in each lamp's cfg.json, not in the build. OTA retains
the filesystem, but a new WLED version can migrate its configuration schema on boot.

## Squid arm waves

`squid/` holds the TycStation squid's arm waves as animated GIFs for the Image effect, one
per lamp shape: `squid-arms-300x1.gif` (the couch strip as one 300-LED segment),
`squid-arms-20x6.gif` (a GLORB's raster), `squid-arms-8x8.gif` (the Moon) and
`squid-arms-30x16.gif` (an Exoy lamp's 30×16 matrix: X is the edge, so every edge shows one colour
along its 16 LEDs and the waves run through the edges in wire order). Each matches its segment's
size, so WLED plays it unscaled. `curtain/squid/mkgifs.py` draws them together
with the curtain's loops. The Image effect plays on one segment per controller.

The files are drawn for a lamp that applies WLED's output gamma of 2.8, as the curtain, the
couch, the Moon and the Exoy lamps do. The GLORBs run gamma 1.0 (`glorb/wled16-port/cfg-overrides.json`), so
`squid-arms-20x6.gif` holds the values that table gives the other lamps: every lamp then puts
the same values on the wire. A lamp whose gamma setting changes needs its file regenerated.

## TycStation effects

[`tycstation_fx`](../usermods/tycstation_fx/) runs the squid's patterns as code: Squid Arms
(the arm waves above), Squid Skin (the curtain's chromatophore cells) and Squid Plankton (the
deep-sea loop's water), on any segment, with Speed, a Sound slider for AudioReactive's volume
and one size slider each. It also registers the TycStation palette as usermod palette 255,
encoded for each lamp's gamma setting at runtime. WLED assigns the effect IDs at boot (142,
169 and 170 on `fleet_esp32` and `fleet_gledopto` and 222 to 224 on `fleet_glorb`, by the
v16.0.1 effect table), so presets name them. The squid figure stays a GIF.

Every lamp runs a build with it. The palette is "TycStation 0" in a lamp's palette list, so
any stock effect can run in the brand colours.

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
`captures/flash/`, checks that the image declares the lamp's release name, uploads
to `/update`, waits for the reboot, then fails unless cfg is unchanged apart from
`vid` and a new usermod block, and presets are byte-identical. On a GLORB, also run
`install --effects glorb/wled16-port/effects.json` afterwards with the same
`--credentials-file`: the port presets need the glorb_fx IDs.

An image without a usermod the lamp had takes that usermod's block in `/json/cfg` `um` with it.
`--usermods AudioReactive,Syslog` names the blocks the image carries (`fleet_*`: AudioReactive
and Syslog; `tycstation_fx` writes none): after the flash the lamp must have exactly these, a block
from before that is not among them may go and the tool names it, and inside a block that stays
every value is compared as without the option. tycpve passes an image's list when its
`wled_flash_images` entry declares one. Without `--usermods` a block that goes is drift.

The release check is the tool's: on the image file, before anything is written, by
the firmware's rule (equal names, a trailing `_V4` ignored); the upload tells the
lamp to skip its own. WLED 16.0.1's own check compares the uploaded name with the
bytes that follow it on the stack (`bufToString` in `wled_metadata.cpp` ends its
copy at the buffer's end, not the name's), so some builds refuse an image of their
own release (TycDodecaRechts, 2026-11-18: `current='ESP32', uploaded='ESP32\xe9…'`).
By then WLED has reset the lamp's segments, and a segment made that way has no
colours or palettes until the lamp restarts. The lamp skips its whole check, so an
image whose description is newer than version 1 is refused too: from version 2 on
WLED also checks which version an update may come from, and the tool does not.
Pass `--skip-validation` only when the release name changes on purpose. After an
upload that ends without the new firmware the tool prints the lamp's answer, then
restarts the lamp, which undoes that reset, and puts its look back; a refusal for
access (OTA lock, PIN, subnet) comes before the reset and leaves the lamp as it
was. A line after the lamp's answer says how the lamp was left.

The fleet's settings PIN and OTA password are stored per device in OpenBao's
`secret/hatyc/creds` by tycpve's `bao:seed-wled-security` job. The private JSON
file contains `pin` and `ota_password`; see
[protected fleet maintenance](../README.md#protected-fleet-maintenance).
The updater temporarily unlocks OTA, restores its protection before checking
configuration, and relocks settings even after a failed upload. If the device
cannot be reached to relock it, recover that device before continuing.

For the reviewed classic-ESP32 upgrades from 0.15.1, 0.15.3 or 0.15.4 only, add
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

The black GL-C-618WL and the DOM-WLE-ADM, both spares at the time, passed this migration and
retained byte-identical presets. The GL-C-618WL
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

One 0.15.4 controller has been flashed with this migration, once: on 2026-11-17 a Gledopto
GL-C-015WL on its factory 0.15.4 image (vid 2508020) was flashed over the air to a 16.0.1 image
(release `ESP32`, an env that extends `fleet_esp32`) with `wledlab.py flash --cfg-migration
0.15-to-16.0.1` at 3d331d6. The tool reported `cfg: matches reviewed migration | presets.json:
byte-identical`, and the controller came back as 16.0.1, release `ESP32`. Before that flash, 0.15.4
was accepted on the sources and on that controller's stored configuration.

WLED v0.15.3..v0.15.4 changes no `cfg.cpp`, `json.cpp` or `set.cpp`. Its `const.h` and
`network.cpp` hunks add Ethernet type 13 (Gledopto), whose board entry v16.0.1 carries unchanged,
and give Ethernet builds GPIO 4 as the default LED pin, which WLED uses whenever no LED output was
created (`FX_fcn.cpp`, `finalizeInit`); the other hunks change the Ethernet env's build defaults
and runtime code (OTA, web UI, Wi-Fi scan, UDP sync parsing, file writes, segment fills,
AudioReactive's PDM clock). Gledopto's published
0.15.4 source (`GLEDOPTO/WLED` branch `gledopto-0.15.4`, one commit on v0.15.4) adds PlatformIO
envs, compile-time defaults (LED pins, type and count, button, relay, microphone, AudioReactive
AGC) and WiZmote buttons 5-7, and changes no `cfg.cpp` either.

The controller checked is a Gledopto GL-C-015WL with Gledopto's factory 0.15.4, release `ESP32`.
It reports the product name `GLEDOPTO`, which that source does not set (its envs set `GLED` and
`GLED_Ethernet`), and Gledopto's `v0.15.4-gledopto` release has no GL-C-015WL image. So its
image was built with a configuration that is not published, and whether it carries other source
changes is not known. Its stored `/json/cfg` has exactly the key paths (list entries compared by
their keys, not their number) of the DOMRAEM's 0.15.1 snapshot this migration
was reviewed on, and those of the Gledopto's 0.15.3 snapshot without `eth`. Its values differ
from both only in leaves the migration leaves as they are, apart from `hw.led.prl` against the
0.15.3 snapshot, which the migration drops whatever its value. It reports the same ESP-IDF
version (`core`, `ESP.getSdkVersion()`: `v3.3.6-16-gcc5440f6a2`) as those two controllers.

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

### Spares, 2026-11-17

Three controllers became spares on 2026-11-17. On 2026-11-18 Spares 1 and 2 became TycDodecaLinks
and TycDodecaRechts (above), and the black GL-C-618WL that had driven both Exoy lamps as TycDodeca
became Spare 4. Spare 3 has no LEDs attached and none of its outputs, buttons, relay or microphone
has been tested, and it has no settings PIN or OTA password (it is not in
`bao:seed-wled-security`). Spare 4 keeps the settings PIN and OTA password of its TycDodeca days
(tycstation/tycpve, controller `dodeca`) and runs the Exoy image `exoy_eth` until it is flashed
with `fleet_gledopto`.

| Spare        | mDNS and syslog host | Hardware                                        | Firmware before its spare days      | Overlay                                                          |
| ------------ | -------------------- | ----------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------- |
| TycLedSpare3 | `tycledspare3`       | Gledopto GL-C-015WL `b0:3f:d3:48:5a:94`         | factory WLED 0.15.1, vid 2507300    | [`overlays/spare3-gledopto.json`](overlays/spare3-gledopto.json) |
| TycLedSpare4 | `tycledspare4`       | Gledopto GL-C-618WL (black) `70:4b:ca:48:91:c8` | `exoy_eth` (TycDodeca), vid 2611140 | [`overlays/spare4-gledopto.json`](overlays/spare4-gledopto.json) |

Spares 1 and 2 (DOMRAEM DOM-WLE-A `70:4b:ca:8f:9c:b4` and `70:4b:ca:8f:a5:a0`, factory WLED 16.0.1,
vid 2605010) are described below as they were set up as spares.

Spares 1 to 3 got `fleet_esp32` of release `fleet-20261115-6e18eb5`: 16.0.1, vid 2611150, release
`ESP32`, 4 MB flash, and `/json/info` lists the usermods AudioReactive and Syslog. The pins,
lengths and types of their outputs, the button, the relay and the microphone are as shipped; on the
GL-C-015WL the 0.15 migration changed how the outputs and buttons are stored (Flash, above):

- DOM-WLE-A: the factory image reports `repo` `guoyanyan25/Wled_v16.0.1_firmware`, release
  `ESP32`. Outputs on GPIO 16 and GPIO 2, 30 LEDs each, both starting at LED 0, so WLED counts 30
  LEDs and both outputs carry the same pixels. Button GPIO 0; relay GPIO 12 with `rev: false`; a
  PDM microphone (type 5) on 26/21 is stored with AudioReactive disabled. By the maker's listing
  the DOM-WLE-A has no microphone, and with that setting AudioReactive read no sound on either board
  (2026-11-18). The two factory
  configurations differ only in the mDNS name and the MQTT client id and topic.
- GL-C-015WL: stock WLED 0.15.1, release `ESP32`. Outputs on GPIO 16 (LEDs 0–29) and GPIO 2
  (LEDs 30–59); button GPIO 17; relay GPIO 18 with `rev: false`; PDM microphone on 32/15 with
  AudioReactive enabled.

The DOM-WLE-A's factory configuration has `ota.same-subnet: true` and no settings PIN. On Spare 1
the first `wledlab.py flash` from another subnet was refused (the controller's message page:
"Access Denied", "Client is not on local subnet.") and changed nothing. Both DOM-WLE-As then got
`{"ota": {"same-subnet": false}}` with `wledlab.py install --cfg` before their flash, which ran:

```sh
python3 wledlab.py flash --host <spare> --mac <mac> --firmware fleet_esp32.bin --release ESP32
```

On both DOM-WLE-As it reported `cfg: unchanged (vid / new usermod block only) | presets.json:
byte-identical`. The GL-C-015WL was flashed with `--cfg-migration 0.15-to-16.0.1` added and
reported `cfg: matches reviewed migration | presets.json: byte-identical`. The image matched the
release's `SHA256SUMS`:

```text
e31f7536052171375f17f8a89c85afb6d00c2fbe5f3a13425c2bdd156de2a695  fleet_esp32.bin (fleet-20261115-6e18eb5)
```

Each spare's overlay holds every key set on it besides the flash, written with
`wledlab.py install --cfg` and read back key by key: `id.name`, `id.mdns` and
`um.Syslog.hostname` as in the table, `def` `{ps: 0, on: false, bri: 16}` (it boots off at
brightness 16) and `ota.same-subnet` false. The DOM-WLE-As got that last key before their flash
(above), the GL-C-015WL after it: the 0.15 migration comes up with it true. Putting a spare into
service needs its role's configuration, a settings PIN and OTA password, and a test of the outputs
the role uses.

## Remote

Every lamp pairs the ESP-NOW remotes tycpve's `wled:remotes` declares, the operator's three:
`704bcac8d198`, `704bcac9aa6c` and `704bcaca4b78`; a lamp ignores any other sender (until
2026-11-10 the second remote was unpaired and moved no lamp; the third was unpaired from 2026-11-11
to 2026-11-18 as an address that belonged to neither remote, until the operator said: "there is a
3rd remote that must be paired with all"; `wledlab.py remotes` shows the last sender a lamp heard).
The overlays that write `nw` (the couch and the two Exoy lamps) carry ESP-NOW on and the same three
remotes, because a `/json/cfg` write with an `nw` block replaces the lamp's paired list. No lamp carries a `remote.json`, so WLED
16.0.1's own handler runs (`remote.cpp`): number button N calls preset N, and on, off, night and
the brightness buttons act on the whole lamp. A lamp with no preset in that slot stays as it is
and logs `error: code=12 (preset does not exist)`. The fallback effects named in `remote.cpp`
are never shown: `handlePresets()` ends in `stateUpdated()`, which reads the effect back from
the segment before anything applies it (`presets.cpp`, `led.cpp`; on 2026-11-10 the couch's
segment did not change on the buttons it has no preset for).

A `remote.json` that sends `{"ps": N}` for those buttons gains nothing and loses two things the
stock handler does: the JSON path skips a preset that is already current (`json.cpp`), and it
does not end the remote's night mode, which then blocks the brightness buttons (`remote.cpp`).

Presets 1 to 7 are the remote's looks on every lamp. The curtain uses this order:

| Button | Curtain look                                    |
| ------ | ----------------------------------------------- |
| 1      | Squid Breathing                                 |
| 2      | Squid Ink Burst                                 |
| 3      | Squid Deep Sea                                  |
| 4      | Squid Chromatophores — dark squid, bright cells |
| 5      | Squid Water — slower drifting background        |
| 6      | PS Fuzzy Noise                                  |
| 7      | TycStation                                      |

Squid Eyes stays available as preset 8 in WLED and Home Assistant. The old curtain presets 2
and 3 were identical; their single remaining copy is 6. On the couch, the Moon, the GLORBs and
the Exoys, slots 1–5 and 8 play the squid's arm waves with matching names; 6 and 7 show their
own looks (on the Exoys Edge Twinklefox and Edge Colorwaves). The Exoys follow the rule since
2026-11-18 (operator: "fully integrate both into house modes etc. also on remotes"): the looks
that stood on their squid slots keep their names and fields in 23 to 28 (Exoy both from 1, Edge
Flow from 2, Edge Aurora from 3, Edge Pacifica from 4, Edge Plasma from 5, Edge Comets from 8),
and the boot playlist 20 plays the same ten looks in the same order.

The GLORBs' installed presets are [`overlays/glorb-presets.json`](overlays/glorb-presets.json).
Every port look (`glorb/wled16-port/presets.json`, the factory's field for field) is preserved:
original slots 1, 2, 3, 4, 5 and 7 live in 7, 6, 18, 15, 16 and 17 respectively. Anything that
is not a look (a boot layout, a test pattern) belongs above 7. The couch's boot layout is
preset 250; in slot 2 it switched the strip off from the remote (2026-11-10).

Every look of the curtain, the couch, the Moon and the GLORBs carries power and brightness
(`"on": true` and `"bri"`: 45, and 200 on the Moon, the operator's values of 2026-11-10): a preset
without them leaves both as they were, so two lamps on the same button stayed apart (the GLORBs at 6
and 255 after one of them rebooted). The files are
[`overlays/glorb-presets.json`](overlays/glorb-presets.json),
[`curtain/presets.json`](../curtain/presets.json),
[`overlays/couch-presets.json`](overlays/couch-presets.json) and
[`overlays/moon-presets.json`](overlays/moon-presets.json).

The Exoys' presets, [`overlays/exoy-presets.json`](overlays/exoy-presets.json) (read from
tycdodeca on 2026-11-11, whose looks stood at 128; tyclab/tycExoyWled's `wled/mkpresets.py` makes
each Exoy lamp's presets from it, keeping the parts on X 0–29, the window lamp's columns, where its
squid looks have their one segment), carry power and no brightness since 2026-11-19 (operator:
"exoy brightness is artefact of stupid agent in the beginning. give full brightness range free.";
from 2026-11-11 every look set 45). A recall, a remote button or a playlist step keeps the lamp's
brightness, and one that turns the lamp on brings back the brightness it had before it was switched
off (WLED 16.0.1 `json.cpp` `deserializeState`, `led.cpp` `toggleOnOff`), so the remote's brightness
buttons (6 to 255), the app and Home Assistant set it across the whole range. Every Exoy preset
carries `"on": true`, the look as much as the playlist and the test pattern: without a brightness it
is what switches a lamp that is off back on. A WLED controller that sends sync in group 1 does not
set their brightness: both overlays set `if.sync.recv.bri` false (the curtain and the couch receive
no sync at all). This holds while the lamp receives colour, effect or palette by sync: with all four
off WLED takes the sender's brightness anyway (`udp.cpp`, `someSel`).

`tests/test_presets.py` holds the presets' rules (power and brightness on every look of the other
lamps; `"on": true` and no brightness on every Exoy preset), `tests/test_cfg.py` the Exoy overlays'
sync setting, and tycpve's `wled:install` puts the files on the lamps.

## Curtain

The Govee H70B5 curtain hangs as three panels of 20 vertical strings × 26 LEDs on the
GL-C-618WL. [`h70b5-gledopto.json`](../curtain/h70b5-gledopto.json) is its configuration
overlay, [`ledmap.json`](../curtain/ledmap.json) its 2D map, generated by
[`mkledmap.py`](../curtain/mkledmap.py); `make lint` fails when the committed map differs
from the generator output. `id.name` is `TycCurtain`; Home Assistant shows the device under the
name set there, "Curtain", which `id.name` does not change. The overlay switches Ethernet off (see Memory) and leaves relay, microphone and Wi-Fi settings alone. Apply it with
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
| 2      | 4    | 520–1039  | middle, over the balcony door    |
| 3      | 12   | 1040–1559 | left                             |

Until 2026-11-17 the overlay put output 2 on GPIO 12 and output 3 on GPIO 4, as on the first
controller on 2026-10-05; the controller read GPIO 4 and 12 on 2026-11-17, and the operator
confirmed that night that every panel shows its part of the picture.

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
[`presets.json`](../curtain/presets.json) keeps that as preset 7 "TycStation", which Home
Assistant's Evening look "TycStation" recalls. Both files upload like the ledmap
(`curl -F "data=@curtain/tycstation.gif;filename=/tycstation.gif" http://<host>/upload`,
the same for `/presets.json`). Rebuild the GIF with the tile removed from the SVG, then
`rsvg-convert -w 840 -h 840 -b black krake.svg -o krake.png` and
`magick krake.png -trim +repage -filter Box -resize 46x40! -modulate 100,140 -level 0%,80% m.png`,
`magick -size 68x42 xc:black m.png -geometry +13+1 -composite -strip tycstation.gif`.
