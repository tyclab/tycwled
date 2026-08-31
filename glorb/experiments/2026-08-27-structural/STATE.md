# Handover: structural comparison, 2026-08-27 (reviewed 2026-08-28)

Lamps: `.160` factory 0.14.4-GLORB.1.3 (reference), `.158` WLED 16.0.1 with the
committed port installed (palettes 0–11, presets, ledmap). Both left on preset 4.
The scripts here run from the repo root with `PYTHONPATH=.`; they import `wledlab`
from the root and resolve their own directory from `__file__`.

## Tooling fixes in this handover (PR "fix/measurement-tooling")

- `hipsim.grids()` applied the ledmap to the liveview stream, which is already
  logical (cell i = `leds[i]`; its always-dark set equals the map's 40 holes,
  not the physical-unmapped set). The old grid was a permutation reading 21
  holes as pixels and never reading raster row 5. **Every `feats`/`blob`/
  `hipsim.stats` number before this fix (`structural.log` rows for 14, 2, 12,
  13; all `hipsearch*.log`) was computed on 59 scrambled cells.**
  `wledlab.metrics` (`act`, `fast`, `hue%`, `hueV`) and the `tartan`/`frizz`/
  `bh`/`colour_sweep` scripts never used `grids` and are unaffected.
- `structural.py` ran its sweep at import time; `pat.py` imports it, so the
  queued candidates crashed on the JSON argv (or would have fired a 12-preset
  sweep). Now guarded; `--offline` re-scores saved captures without the lamps.
- Current was read in two consecutive 22 s windows (12 s in `pat.py`) — at
  different phases of a 30–50 s colour cycle. `pwr_both` reads both lamps
  alternately over 100 s. Old `pwr … ratio` lines in `structural.log` are noise.
- `captures/` is created; the capture is saved before scoring; the lamps are
  restored to preset 4 in a `finally`. `wledlab.upload` raises on curl failure.
- `pat.py`: the "single segment" flag was computed once per preset and applied
  to every candidate; it is now an explicit `"single": true` per candidate.
  Palettes 12–15 are uploaded from named files in this directory and read back.
- `after_*.sh` pointed at a non-existent clone path without `|| exit`.

## Result so far

Owner's eye: presets 1, 3, 4, 5, 2 accepted; **14 rejected** ("does not match").
`make verify` was reported 12/12 PASS on main, but no verify log is committed
and the gate is a 70 s current-sum ratio (see "Open method flaws"). The
2026-08-27 sweep read p1 at 0.79 and p3 at 1.30 with the old sequential
windows; p3 had read 0.74 in `colour_sweep.log` — re-run `verify` with ≥100 s
before quoting a pass.

Structural sweep, 100 s per preset, corrected `grids` (`structural-rescore.log`
from the saved `captures/struct-pN.json`; `cells 80/80` on every row):

| preset                 | swell tstd / sstd (ref / port)           | act (ref / port) | notes                                                             |
| ---------------------- | ---------------------------------------- | ---------------- | ----------------------------------------------------------------- |
| 1 Colorwaves – Analog. | 0.152/0.163 · 0.195/0.148                | 0.278/0.266      | port mean 0.394 vs 0.507; vhist port skewed dark (bands 0: 29→13) |
| 3 Colorwaves – Sunset  | 0.122/0.120 · 0.139/0.140                | 0.225/0.229      | matched on every stat                                             |
| 4 Running – Atlantica  | 0.092/0.089 · 0.244/0.241                | 0.383/0.381      | matched                                                           |
| 5 Running – Analogous  | 0.095/0.093 · 0.297/0.307                | 0.537/0.556      | matched                                                           |
| 7 Frizzles – Analogous | 0.024/0.031 · 0.195/0.169                | 0.239/0.195      | port fast 0.550 vs 0.345; mean 0.110 vs 0.087                     |
| 9 Frizzles – Fire      | 0.066/0.077 · 0.170/0.156                | 0.237/0.265      | close                                                             |
| 10 Black Hole – Tert.  | 0.026/0.039 · 0.188/0.237                | 0.212/0.310      | **hue census unmatched** (peak bin 0 vs 3), huespread 65.8/31.4   |
| 11 Black Hole – Sunset | 0.020/0.013 · 0.145/0.132                | 0.210/0.222      | hue matched; port swell half the fork's                           |
| 14, 2, 12, 13          | old rows in `structural.log` are pre-fix | —                | **re-capture**; their captures are not in this clone              |

The pre-fix p14 row (fork 18 % black / 21 % full, port 0 % black) is probably
still directionally right — the port floors seg 0 at grey 130 — but it has to
be re-measured before it is used.

## Re-measurement + first gate artifact (2026-08-31)

Full 12-preset sweep with the fixed tooling (`structural-remeasure.log`, captures
committed as `captures/struct-pN.json.gz`) followed by the first structural
`verify` run (`verify-remeasure.log`, presets sha256 in its header):

- **verify: FAIL ['7', '10', '12', '14']** — every owner-accepted preset PASSes,
  every known-or-suspected mismatch FAILs. Tolerances (vhist 0.25, hue EMD 0.45,
  sstd 1.6x, act 1.4x, current 15 %) held without adjustment.
- p1 PASSes on every criterion after the palette0 restore — closing the
  incident above with a live measurement.
- p7 FAIL current 1.15: the tolerance-edge `bri 200` choice plus stock's
  8-frizzle floor (`lit_r 1.46`). Decide per the README criterion (peak/lit),
  not by re-tuning bri to the current gate.
- p10 FAIL hue 1.12 + act 1.46: the Black Hole colour path is really wrong —
  the arcsine-dwell model and the port palette agree with each other but not
  with the fork (its stars dwell far more in the red end). Needs an index-dwell
  reconstruction from `captures/struct-p10.json.gz`, not another census fit.
- p12 FAIL hue 0.46 (tol 0.45): borderline pastel drift on Fairy Reaf — owner
  call whether this is the accepted no-boost residual or a defect.
- p14 FAIL vhist 0.37 + sstd 0.43: the rejection reproduces on the corrected
  grid. Fresh numbers: fork 20 % of samples below V 0.2 and 21 % above 0.9
  (bimodal, peak 0.97), port 0 % below 0.2 and 8 % above 0.9 (unimodal
  mid-grey, peak 0.68); spatial std 0.220 vs 0.094. The queued
  single-segment candidates (`after_pat.sh`) remain the open fix.
- Lamps were found OFF before the run and were switched off again after it.

## Preset 14 — what is known and what is not

- The fork's Hiphotic slider names come from the public firmware binary
  (`snrgy-studios/GLORB-WebInstaller`, `strings` of `GLORB_0_14_4-1_3`):
  `Hiphotic@Speed,Hue variation,X scale,Y scale` → fork `sx` = Speed,
  `ix` = Hue variation, `c1`/`c2` = X/Y scale, `c3` unused. Factory preset 2:
  `sx 72, ix 14, c1 128, c2 128`; preset 14: `sx 52, ix 128, c1 64, c2 190`.
  So "Hue variation 14 vs 128" is sourced — but `c1` and `c2` differ too, and
  the bimodal brightness has not been attributed to `ix` alone. The fork
  source is not public; `snrgy-studios/WLED-SNRGY` is an untouched mirror.
- Stock fx 180 (WLED 16 `FX.cpp` `mode_2DHiphotic`) is `sx` = X scale,
  `ix` = Y scale, `c3` = speed (5-bit, larger = slower), `c1`/`c2` unused,
  palette index spatial, full brightness. The port's `sx/ix 32` are therefore
  spatial scales, not the fork's Speed/Hue variation. Finest local period at
  `sx 255` on 20 columns ≈ 6–7 cells; along y at `ix 255` the pattern never
  completes a period over 6 rows.
- "A brightness pattern × uniform colour cannot produce that" is **not
  proven**: the 0 % black follows from the chosen floor 130 / `bri 230`.
  `hipsearch*.log` rankings are inside replicate noise (`c3` 54/40/70 are the
  same configuration — 5-bit — and scored 2.23/2.37/2.42, the whole candidate
  range) and were scored on the scrambled grid.

Queued candidates (files and exact commands in `after_struct.sh` for preset 2,
`after_pat.sh` for preset 14 — both now runnable, 100 s per candidate):

1. preset 2 pattern layer: Noise2D `ix` 35/50, `sx` 0/80 on steep/linear grey
   palettes (188/187) vs Hiphotic 255/255 floor 0 vs current.
2. preset 14 as one segment (`"single": true`): Hiphotic `sx/ix` 112 | 255 |
   180, `c3` 31, on plain Fire-span palettes 186 (112–224) / 185 (64–224);
   plus Noise2D `ix` 35. If accepted: preset 14 becomes one segment,
   `mkpalettes.py` needs a `plain` + span mode, `make verify`, PR.

## Palette0 incident (2026-08-31)

The port lamp's `/palette0.json` (ID 200, used only by preset 1) was found
holding **palette4.json's content** (Tertiary layer); the other 11 slots were
byte-correct. The 2026-08-27 p1 capture showed the Tertiary census and lower
luma on the port — the "port too dark" p1 finding was this file, not the port
design. Restored byte-exact from `glorb/wled16-port/palette0.json` (readback
verified); the 2026-08-31 re-measurement then read p1 matched (ratio 1.02,
hue census identical). Lesson enforced by the new gate: `verify` now records
`cpalcount` and firmware/state provenance, and `install` remains the only
sanctioned way to change lamp files. The pre-fix p1 capture was overwritten
by the re-measurement; its census lives in `structural-rescore.log` and the
review notes.

## Loop closures (2026-08-31, branch loops/close-review-cycles)

1. Gate: `verify` adds structural criteria (V-histogram L1/2, circular-EMD
   hue distance, spatial-std ratio, activity ratio, peak/lit ratios reported)
   computed from a liveview capture taken in the same window as the alternating
   current samples; header stamps the presets.json sha256 and both lamps'
   firmware/fps/maxpwr/cpalcount. `--current-only` keeps the legacy behaviour.
   Tolerances are provisional until calibrated on the 2026-08-31 sweep.
2. Searches: `pat.py` reads back every swept parameter (clamped/ignored keys
   abort) and takes a replicate count (`pat.py '<plan>' 3`) so rankings can be
   compared against their own spread.
3. Captures: `captures/*.json.gz` are committable (`.gitignore` narrowed);
   the sweep backing any committed verdict gets committed alongside it.
4. Frizzles: acceptance restated as peak/lit vs the fork (README), frozen.
5. Provenance: every capture now embeds firmware, fps, maxpwr, cpalcount and
   the full segment state of both lamps.

## Open method flaws (review 2026-08-27, partially addressed above)

- The gate: `leds.pwr` is a post-brightness channel sum — a first moment,
  invariant to redistribution. It passed preset 14 (0.98), preset 11 with
  `act 0.210/0.087` (`census_long.log`) and preset 10 with the hue-census peak
  in a different bin. `compare` has no threshold or exit code. Add structural
  tolerances (V-histogram distance, `sstd`, activity, circular hue distance)
  to `verify`, default it to ≥100 s, and commit its log.
- Band shares and `fast_share` are normalised per lamp (denominator confound);
  zero-order-hold resampling inflates band 4 by ~50–65 %; band 0 (<0.1 Hz) is
  not resolvable in 100 s. `activity` divides by a per-lamp lit set and does
  not normalise Δt. `hue_census` splits red across bins 0/11 and thresholds
  at 0.05 while `metrics` uses 0.2; `hue_spread` falls back to black cells.
  Autocorrelations are biased (long lags depressed — the 35 s hue cycle).
  Brightness is `max(RGB)`, not luma. `blob()` scores a uniform row as 0 and
  deletes holes instead of masking them.
- `mkpalettes.py` assumptions stated as measured: the sine-dwell shares per
  palette eighth have no log (only a self-test of the arcsine model); Fire
  span 112–224 is one census number fitting two parameters; Tartan ×1.4 was
  never measured at `g 255`; preset 2 floor committed 150 vs fitted 130;
  Frizzles 7 `bri 200` has no log and was chosen at the tolerance edge.
- Provenance: scripts do not record the lamps' segment state or
  `info.leds.fps` (liveview load differs: 17.2 vs 22.6 Hz measured); no error
  bars. Split-half on p10/p11 captures: fast presets repeat within 6 %; the
  slow presets (14, 2, 12, 13) are untested.

## Firmware facts verified against upstream (v16.0.1 / v0.14.4)

- `custom3` is 5-bit on **both** firmwares (`FX.h`, `json.cpp` constrain) —
  factory presets with `c3` > 31 clamp on the fork too.
- `load16()` is bit-exact against 16's `fastled_slim` and FastLED 3.6 on all
  six factory palettes. Colorwaves sweeps 0–127 with NOWRAP (16: `(i*240)>>8`;
  0.14: `scale8(i,240)`); the Palette effect is linear in time (flat dwell);
  Noise2D reads the palette with wrap and no remap.
- `bm 6` = multiply: `lerp(bottom, top×bottom/255, seg1.bri)` — seg 1 `bri` is
  a mix weight, not a dim; keep it 255.
- Liveview is logical on both firmwares. 0.14's is post-global-`bri` (captures
  run at 255) and gamma-encoded only for segment colours and _custom_
  palettes; the factory presets use built-in palettes, so V is comparable.
  `leds.pwr` is the post-brightness, post-gamma channel sum + standby.
- The fork's Colorwaves is a modified 2D/audio variant (`2vg` flags), so the
  stock 0–127 model may not describe its sweep.
- WLED 16 reloads `/palette*.json` on upload; delete with
  `/edit?func=delete&path=/paletteN.json`, then upload any palette to reload.
  The lamp currently holds only palettes 0–11.
