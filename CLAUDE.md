# tycwled — working rules

Port of the GLORB lamp (closed WLED 0.14.4 fork) to stock WLED 16 with measured, gated
equivalence. Read README.md first; the reversing record lives in
`glorb/experiments/2026-08-31-reversing/NOTES.md`.

## The one rule that has bitten every shortcut

**The gate confirms, it never searches.** Do not iterate fixes against `make verify` (flash,
measure, theorize from the metric signature, tweak, repeat) — the gate has been satisfied by
cancelling errors twice in this repo's history. When port output differs from the factory lamp:
prove the mechanism first, offline, against ground truth — the factory dump in
`glorb/factory-0.14.4-GLORB.1.3/`, the disassembly in NOTES.md, or an offline model
(`glorb/experiments/2026-08-31-reversing/blackhole_model.py` is the worked example) — then flash,
then let the gate confirm. Never widen a tolerance to make a preset pass; tolerance changes are
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
  comparable and `verify` gates on the current ratio.
- 0.14 writes effects THROUGH the ledmap: the 40 unmapped cells drop writes and read black —
  energy sinks in fade/blur loops. The usermod reproduces this via `glorb_cellMapped()` in
  `glorb_fx.cpp`; do not remove that gating.
- The six fork effects live at fx 189–193 and 195 (194 is stock Swirl). On the port they are
  auto-assigned 142/169/170/171/220/221 — `glorb/wled16-port/effects.json` pins the mapping and
  `install --effects` asserts it against the lamp; a WLED version bump can renumber them.
- Measure over >= 100 s: colour cycles run 30–50 s and short windows swing hue phase +-25 %.
- Liveview is pre-gamma on both firmwares; it cannot see the output stage — only the current
  ratio can.

## Workflow

- `make lint test check-palettes check-ledmaps` before pushing; `make verify REF=<factory lamp>
TARGET=<port lamp>` is the acceptance gate (~24 min, occupies both lamps, restores presets).
- PR-only main, merge commits. Verify evidence: commit the gate log (see
  `glorb/experiments/2026-08-31-reversing/verify-*.log`); capture JSONs stay untracked.
- NEVER commit anything under `glorb/firmware/` or `*/segments/` — carved vendor firmware, not
  redistributable. gitignored; keep it that way.
- `wledlab.py` is stdlib-only; keep it that way.
