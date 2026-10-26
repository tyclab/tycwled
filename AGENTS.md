# tycwled — working rules

Port of the GLORB lamp (closed WLED 0.14.4 fork) to stock WLED 16 with measured, verified
equivalence. Read README.md first; the reversing record lives in
`glorb/experiments/2026-08-31-reversing/NOTES.md`.

## The one rule

**`make verify` confirms a fix; it is not a search tool.** Do not iterate fixes against `make verify` (flash,
measure, theorize from the metric signature, tweak, repeat) — `make verify` can pass on
cancelling errors. When port output differs from the factory lamp:
prove the mechanism first, offline, against ground truth — the factory dump in
`glorb/factory-0.14.4-GLORB.1.3/`, the disassembly in NOTES.md, or an offline model
(`glorb/experiments/2026-08-31-reversing/blackhole_model.py` is the worked example) — then flash,
then let `make verify` confirm. Never widen a tolerance to make a preset pass; tolerance changes are
argued from `wledlab.py rescore` over saved captures, offline.

## Verbatim, not fitted

Factory bytes are the reference everywhere: palettes ship the factory stops byte-exact
(`glorb/mkpalettes.py`), presets are the factory file field-for-field except `fx`/`pal`, and the
tests (`tests/`) enforce all of it — palette verbatim-ness, preset identity, effect-name/id
agreement. If something looks wrong, the fix is never to re-fit these files; find the mechanism
(gamma, palette re-encoding, helper rounding, ledmap topology — all documented in NOTES.md).

## Facts that are easy to get wrong

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

## Workflow

- `make lint test check-palettes check-ledmaps` before pushing; `make verify REF=<factory lamp>
TARGET=<port lamp>` is the acceptance check (~24 min, occupies both lamps, restores presets).
- PR-only main, merge commits. Verify evidence: commit the verify log (see
  `glorb/experiments/2026-08-31-reversing/verify-*.log`); capture JSONs stay untracked.
- NEVER commit anything under `glorb/firmware/` or `*/segments/` — carved vendor firmware, not
  redistributable. gitignored; keep it that way.
- `wledlab.py` is stdlib-only; keep it that way.
- Our lamps run `fleet/` builds (stock WLED updates would drop the syslog usermod): build
  with `fleet/build.sh`, flash one lamp at a time with `wledlab.py flash`, which refuses
  cfg or preset drift.
- The curtain effect census of 2026-10-07 (census, scored frames, DDP strobe capture and its
  tools) is archived outside git in `~/.local/share/tycwled/census-2026-10-07/`; its
  `ARCHIVED.md` lists the known defects. PR #30 closed it unmerged.

## Maintenance

- README files and agent instruction files are exempt from the comment limit
  by design. The limit applies to code and configuration files.
- Outside the limit (operator, 2026-10-08): vendored third-party code and
  third-party build output (kept byte-identical to upstream), Hugo site
  functional files, translation files, example/template configs whose comments
  document the schema, files under ten code lines, and approved runtime text
  such as MCP tool docstrings. Output of our own generators is inside it: fix
  the generator.
- Keep code comments at or below 20% of nonblank lines per file. Preserve tool
  directives, licenses and runtime descriptions; only the operator may grant a
  documented exception above the limit.
- Keep repository guidance in this `AGENTS.md`. Update README process/logic
  diagrams with behavior changes and verify commands against the code.
- Remove features or files only with evidence they are unused and checks showing
  existing behavior is preserved.
