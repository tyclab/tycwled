# Handover: structural comparison, 2026-08-27

Lamps: `.160` factory 0.14.4-GLORB.1.3 (reference), `.158` WLED 16.0.1 with the
committed port installed (palettes 0–11, presets, ledmap). Both left on preset 4.
The scripts here ran from the repo root with `PYTHONPATH=.`; `./` in them is this
directory (they import `wledlab` from the root and `hipsim` from here).

## Result so far

`make verify` on main: 12/12 PASS (0.92–1.11). Colour matched per hue census.
Owner's eye: presets 1, 3, 4, 5, 2 accepted; **14 rejected** ("does not match").

Structural sweep (`structural.py`, 100 s per preset, `structural.log`), done for
14, 2, 12, 13 before the handover; 10, 11, 7, 9, 1, 3, 4, 5 still to run:

| preset                 | structure                                                                             | verdict         |
| ---------------------- | ------------------------------------------------------------------------------------- | --------------- |
| 14 Hiphotic – Fire     | fork pixels bimodal (18 % black, 21 % full), spatial std 0.215; port 0 % black, 0.092 | **not matched** |
| 2 Hiphotic – Tertiary  | spatial std 0.113/0.126, swell 0.185/0.174, activity 0.186/0.190                      | close           |
| 12 Tartan – Fairy Reaf | 0.305/0.27, swell 0.07/0.084, activity 0.37/0.34                                      | close           |
| 13 Tartan – Analogous  | 0.275/0.26, swell 0.102/0.102                                                         | matched         |

## Why 14 fails — the finding

The fork's Hiphotic maps its spatial sin/cos pattern to the **palette index**:
"Hue variation" is the spatial index spread. Preset 2 uses 14 (near-uniform
colour → the multiply composite is right). Preset 14 uses **128**: half the
Fire palette (black → orange) is spread across the lamp as blobs, and the
global cycle moves it through the palette. A brightness pattern × uniform
colour cannot produce that. Frame renders: `PYTHONPATH=. python3 -c` over
`captures/census-p14.json` (see `hipsim.grids`).

## Queued but not run (lamps freed for the handover)

1. `pat.py` on preset 2: Noise2D (fx 146, `ix` 35/50, `sx` 0/80) with a steep
   grey pattern palette (`pattern-steep-188.json` → upload as `/palette12.json`)
   vs Hiphotic 255/255 floor 0 vs current. Scores contrast, blob length, swell.
   Exact candidate JSON: `after_struct.sh` (preset 2) and `after_pat.sh`
   (preset 14); run the `python3 pat.py '...'` line directly, no waiting loop.
2. `pat.py` on preset 14 as a **single segment** (drop the colour layer):
   Hiphotic fx 180 `sx/ix` 112 | 255 | 180, `c3` 31, on a plain (non-mirrored)
   Fire-span palette `fire-span-112-224-plain-186.json` (upload as
   `/palette14.json`, ID 186) or `fire-span-64-224-plain-185.json` (ID 185);
   plus Noise2D `ix` 35 on the same palette. `pat.py` drops seg 1 automatically
   for single-segment candidates.

Expected: the single-segment Hiphotic reproduces black gaps and full-orange
blobs; blob size is limited (stock finest period 16 cells at scale 255, fork
~4–7 cells). If accepted: preset 14 becomes one segment, palette 5 becomes a
plain span palette (`mkpalettes.py` needs a `plain` + span mode), `make verify`,
PR.

## Facts learned today (also in README "GLORB facts")

- WLED 16 stores `custom3` in 5 bits — every `c3` > 31 silently runs at 31.
- Windows: census and current over ≥ 3 colour cycles (100 s); 10–40 s swings ±25 %.
- Delete lamp files with `/edit?func=delete&path=/paletteN.json`, then upload any
  palette to reload the list. The lamp currently holds only palettes 0–11.
- Black Hole: fork keeps stock slider positions; Intensity = palette range.
- Tartan adds its two line sets: crossings clip(2·C) → Analogous layer ×1.4.
- Frizzles 7 is current-bound (stock draws 8 frizzles over 1.6× the cells).
- Composite layers show ~10 points more blue than the fork — 8-slot chord, not dwell.
