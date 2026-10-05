#!/usr/bin/env python3
"""Generate curtain/ledmap.json: the H70B5 curtain on a grid of its measured string positions.

LEDs 0-519 are the right panel (seen from the room), 520-1039 the middle, 1040-1559 the left;
each is 20 vertical strings of 26, top first, non-serpentine, string 0 on the panel's right,
all three panels level. `--check` verifies the committed file instead of writing it (make lint).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ledmap.json")

PANELS, STRINGS, LEDS = 3, 20, 26
# string (0 = leftmost seen from the room) -> x px on a straight-on photo 4000 px wide;
# every 5th string and each panel's last were lit, the strings between are interpolated
LIT = {0: 740.3, 5: 998.4, 10: 1219.5, 15: 1379.5, 19: 1529.9, 20: 1571.7, 25: 1717.8, 30: 1880.7,
       35: 2037.2, 39: 2180.9, 40: 2223.4, 45: 2407.4, 50: 2574.2, 55: 2749.2, 59: 2880.7}
# one grid cell = the door panel's string spacing; LED rows hang 53 px apart in every panel
UNIT, ROW = 32.0, 53.0


def string_px(s):
    lo = max(k for k in LIT if k <= s)
    hi = min(k for k in LIT if k >= s)
    return LIT[lo] if lo == hi else LIT[lo] + (LIT[hi] - LIT[lo]) * (s - lo) / (hi - lo)


def columns():
    # left to right, rounded to the grid, never onto the previous string's column
    cols, prev = [], -1
    for s in range(PANELS * STRINGS):
        prev = max(int((string_px(s) - LIT[0]) / UNIT + 0.5), prev + 1)
        cols.append(prev)
    return cols


def build():
    cols, cells = columns(), {}
    for led in range(PANELS * STRINGS * LEDS):
        panel, k = divmod(led, STRINGS * LEDS)
        string, row = divmod(k, LEDS)
        x = cols[(PANELS - 1 - panel) * STRINGS + (STRINGS - 1 - string)]
        y = int(row * ROW / UNIT + 0.5)
        if (x, y) in cells:
            raise SystemExit(f"LED {led} on cell {x},{y}: taken")
        cells[(x, y)] = led
    return cells


def render(cells):
    width = max(x for x, _ in cells) + 1
    height = max(y for _, y in cells) + 1
    grid = [cells.get((x, y), -1) for y in range(height) for x in range(width)]
    # compact: WLED 16 scans the raw file for the exact bytes "map":[
    text = json.dumps({"n": "curtain", "width": width, "height": height, "map": grid}, separators=(",", ":"))
    return text, f"{width} x {height}, {len(cells)} of {len(grid)} cells mapped"


def main():
    text, summary = render(build())
    if "--check" in sys.argv:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print(f"ledmap.json: {summary} {'ok' if ok else 'STALE -- rerun mkledmap.py'}")
        if not ok:
            sys.exit(1)
    else:
        open(OUT, "w").write(text)
        print(f"ledmap.json: {summary} written")


if __name__ == "__main__":
    main()
