# glorb_fx — GLORB factory effects for WLED 16

Reimplements the six custom effects the GLORB factory presets use (fork fx
189–195: Colorwaves, Running, Frizzles, Black Hole, Hiphotic, Tartan) as a
WLED 16 `custom_usermods` usermod, so the port lamp runs the same algorithms
as the factory fork instead of stock lookalikes.

Slider layouts come verbatim from the fork binary's effect metadata strings.
Effect bodies start from the stock WLED 0.14.4 (MIT) ancestors and are
corrected against the decompiled fork functions
(`glorb/experiments/2026-08-31-reversing/NOTES.md`); every spot still awaiting
that correction is marked `TODO-REVERSE`.

Build (WLED checkout at the port lamp's release tag, usermod symlinked in):

```sh
git clone --depth 1 --branch v16.0.1 https://github.com/wled/WLED.git
ln -s /path/to/tycwled/glorb/usermod/glorb_fx WLED/usermods/glorb_fx
# platformio_override.ini: extends env:esp32s3dev_8MB_qspi, custom_usermods = glorb_fx
pio run -e glorb_port
```

The effects register with `addEffect(255, …)` — WLED assigns the final fx IDs
at boot; read `/json/eff` after flashing and point the port presets at those
IDs. Display names intentionally match the fork (they duplicate stock names in
the effect list; the presets reference IDs, not names).
