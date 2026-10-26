# Measurement and firmware traps

Read for this topic; paths below are relative to the repository root unless stated otherwise.

- WLED 16 gammas every rendered pixel; the fork does not. The port runs `gc` 1.0
  (`glorb/wled16-port/cfg-overrides.json`). With matched gamma, the lamps' own mA estimates are
  comparable and `verify` checks the current ratio.
- 0.14 writes effects THROUGH the ledmap: the 40 unmapped cells drop writes and read black —
  energy sinks in fade/blur loops. The usermod reproduces this via `glorb_cellMapped()` in
  `glorb_fx.cpp`; do not remove that gating.
- The six fork effects live at fx 189–193 and 195 (194 is stock Swirl). On the port they are
  auto-assigned 142/169/170/171/220/221 — `glorb/wled16-port/effects.json` pins the mapping and
  `install --effects` asserts it against the lamp; a WLED version bump can renumber them.
- The GLORB's PDM mic (ESP32-S3) is silent unless `glorb/usermod/glorb_fx/platformio_override.ini`
  sets `-D I2S_USE_16BIT_SAMPLES`: with 32-bit samples it reads `PDM digital - quiet`, AGC pinned
  at exactly `1.00 x`, GEQ black. Measured, mechanism unproven — the `/ 65536.0f` downscale is a
  float divide, not a truncation, so it is not the explanation. Keep the flag across WLED bumps.
- Prove a mic with AGC gain correlated against an independent sound meter, with a known-good mic
  as positive control. `peak %` is post-AGC and frame-change is gated on `sampleAvg > 0.25` — both
  produced false positives, and a working mic scores near zero on `peak %`.
- Measure over >= 100 s: colour cycles run 30–50 s and short windows swing hue phase +-25 %.
- Liveview is pre-gamma on both firmwares; it cannot see the output stage — only the current
  ratio can.
- Set a preset with `POST /json/state {"ps":N}`; a Home Assistant `light.turn_on` overrides it.
  One measurement job per lamp at a time. WLED silently ignores a JSON POST without
  `Content-Type: application/json` (a bare `curl -d`).
- WLED 16's Swirl (fx 175 on the fleet builds) is the 2D audio-reactive one (fxdata
  `!,Sensitivity,Blur;,Bg Swirl;!;2v;ix=64,si=0`): `ix` is Sensitivity, `c1` Blur is the only
  trail decay (0 accumulates into a solid fill; the UI applies 128 when picked). With
  AudioReactive on and a quiet mic it draws nothing new. `{"AudioReactive":{"enabled":false}}`
  on `/json/state` (not `on`, though the readback reports `on`) hands it to the sound
  simulation `si`; the toggle is not persisted. The 4th fxdata field holds the flags (`2` = 2D,
  `v`/`f` = needs audio): read it before judging an effect in a silent room. `fxdef:true` on a
  segment applies the effect's own slider defaults.
- The curtain answers `/json/live` with 501. Its websocket liveview (`wledlab.py capture`)
  arrives downsampled 2:1 per row (1428 cells) at about 10–12 Hz, so strobes above ~5 Hz
  alias; Solid lights 27.3 % of those cells, so normalise coverage by that.
- Over a tunnel with a small MTU, large frames vanish without an error: DDP at 1440 data bytes
  per packet lit three rows, ≤ 1200 lit the panel, and `/json/info`, `/json/cfg`, `/json/eff`
  hang while `/json/state` works. Keep DDP packets ≤ 1200 bytes; use an HTTP client that sets
  `TCP_MAXSEG` around 1100.
- Identify a controller by MAC or IP (`/json/info`) before any write, never by role words:
  boxes changed roles on 2026-10-07 (`fleet/README.md`).
