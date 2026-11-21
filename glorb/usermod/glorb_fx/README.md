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

The framework's ESP32-S3 SDK is prebuilt for a 16 KB instruction cache. The code
one WLED 16 main-loop pass touches does not fit it, so every pass fetches most of
its code from flash again: 549 loops/s, against 3,022 with 32 KB (one image, the
cache switched every 8 s in one boot, 2026-11-21). WLED's AudioReactive advances
the microphone baseline once per loop pass, so the loop rate also sets how the
lamp follows sound.

`icache_32kb.py` (a PlatformIO pre-script in the override) links against a copy
of the framework's `memory.ld` whose RAM code starts after both cache banks and
defines `GLORB_ICACHE_32KB`; the usermod then keeps the second bank's RAM
(0x40374000–0x40378000) out of the heap and switches the cache in `setup()`. The
three belong together: the define comes from the script only, the usermod
refuses to switch when RAM code still starts below 0x40378000, and
`fleet/check_glorb_icache.py` checks the built image. The cost is 16 KB of RAM.
The info page's "Main loop" row shows the loop rate and the cache size.
