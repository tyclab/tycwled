# glorb_fx — GLORB factory effects for WLED 16

Reimplements the six custom effects the GLORB factory presets use (fork fx
189–193 and 195: Colorwaves, Running, Frizzles, Black Hole, Hiphotic, Tartan) as a
WLED 16 `custom_usermods` usermod, so the port lamp runs the same algorithms as
the factory fork instead of stock lookalikes. All twelve factory presets use
these effects and none other.

Slider layouts come verbatim from the fork binary's effect metadata strings.
Effect bodies start from the stock WLED 0.14.4 (MIT) ancestors and are corrected
against the decompiled fork functions — the disassembly, the derivation and the
per-effect confidence are in
`glorb/experiments/2026-08-31-reversing/NOTES.md`.

Colorwaves and Running have Sound Reactive branches (`o1`), lifted from the same
disassembly, so `audioreactive` must be built in alongside this usermod. The
factory presets all ship with `o1` off, but the branches are there.

Build (WLED checkout at the port lamp's release tag, usermod symlinked in):

```sh
git clone --depth 1 --branch v16.0.1 https://github.com/wled/WLED.git
git -C WLED apply /path/to/tycwled/fleet/patches/glorb-mic-filter.patch
git -C WLED apply /path/to/tycwled/fleet/patches/glorb-pdm-envelope.patch
ln -s /path/to/tycwled/glorb/usermod/glorb_fx WLED/usermods/glorb_fx
cp /path/to/tycwled/glorb/usermod/glorb_fx/platformio_override.ini WLED/
cd WLED && pio run -e glorb_port
```

The effects register with `addEffect(255, …)`, which fills the reserved gaps in
WLED's mode table before appending — so the IDs are assigned at boot and four of
the six land _below_ `MODE_COUNT`. On WLED 16.0.1 they come out as 142
Colorwaves, 169 Running, 170 Frizzles, 171 Black Hole, 220 Hiphotic, 221 Tartan.
Read `/json/eff` after flashing and point the port presets at whatever IDs your
build assigned.

Display names intentionally match the fork, so they duplicate stock names in the
effect list; the presets reference IDs, not names.

## Instruction cache

The framework's ESP32-S3 SDK is prebuilt for a 16 KB instruction cache, and the
main loop of this build runs about five times slower with it than with 32 KB.
Measured on one ESP32-S3 board on 2026-11-21:

| Image                                                                          |           16 KB |               32 KB |
| ------------------------------------------------------------------------------ | --------------: | ------------------: |
| `fleet_glorb`, two flashes of the same source, eight reads each                | 629–663 loops/s | 3,010–3,055 loops/s |
| Instrumented build with stage timers, the cache switched every 8 s in one boot |     549 loops/s |       3,022 loops/s |

In the instrumented build a call repeated at once took 84 µs instead of 278 µs
with 16 KB and the same time with 32 KB, which is why the cause is read as code
fetched from flash again on every pass; cache misses themselves were not counted.

The cache size changes one part of how this build follows sound. The microphone
baseline runs on its own clock (`fleet/patches/glorb-pdm-envelope.patch`), and
with that clock at 467 µs the Running effect answered a lasting tone at the same
time with either cache size (345 Hz: 13.95 s with 16 KB, 13.93 s with 32 KB).
AudioReactive's limiter after it (rise and fall time, 80 and 1,400 ms on the
lamps) runs once per loop pass and counts every call as at least 1 ms, so above
1,000 passes a second the volume rises and falls faster than configured. On the
same bench recordings, 0.85 to 1.10 s after the tone stopped, Running advanced
this many steps per frame:

| Tone     | 16 KB, 467 µs | 32 KB, 467 µs | 32 KB, 429 µs | Factory image, the three paired runs |
| -------- | ------------: | ------------: | ------------: | -----------------------------------: |
| 345 Hz   |          2.72 |          0.91 |          0.99 |                     0.95, 1.05, 0.94 |
| 1,378 Hz |          2.68 |          1.10 |          1.00 |                     0.98, 1.00, 0.93 |

Without the envelope patch WLED's AudioReactive also advances the baseline once
per loop pass. The 429 µs clock was timed with sound transmission off, as the
lamps run; with sound sync sending the build uses the same clock, and its match
to the factory image is not measured.

`icache_32kb.py` (a PlatformIO pre-script in the override) links against a copy
of the framework's `memory.ld` whose RAM code starts after both cache banks and
defines `GLORB_ICACHE_32KB`; the usermod then keeps the second bank's RAM
(0x40374000–0x40378000) out of the heap and switches the cache in `setup()`. The
three belong together. The define comes from the script only. After linking, the
script reads the ELF and stops the build when RAM code starts inside the second
bank, when the switch function does not lie in RAM or when the bank is no record
of the heap's table of reserved memory; with the define and the stock layout the
image would stop in heap start-up on every boot. `fleet/check_glorb_icache.py`
checks the released pair: the image whole (segments, checksum, SHA-256) with its
RAM code after both banks, and the same ELF checks on the ELF the image names as
its source. Free heap is about
17 KB lower (188 KB against 171 KB on the bench). The info page's "Main loop" row
shows the loop rate and the cache size read back from the chip.

OTA in both directions worked on the bench board: from release 2611202 (16 KB
layout) to this build and from this build back to 2611202, each with one CPU
reset and an answer 5 s later. Not tested: the lamps on the wall.
