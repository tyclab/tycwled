#!/usr/bin/env python3
"""Generate curtain/ledmap.json: the H70B5 curtain on a 60 x 40 grid in true proportions.

LEDs 0-519 are the right panel (seen from the room), 520-1039 the middle, 1040-1559 the left;
each is 20 vertical strings of 26, top first, non-serpentine, string 0 on the panel's right.
`--check` verifies the committed file instead of writing it (make lint).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ledmap.json")

PANELS, STRINGS, LEDS = 3, 20, 26
WIDTH = PANELS * STRINGS
# vertical LED pitch over string pitch (photo: 1.4-1.6), so shapes keep true proportions
ROW_PITCH = 1.5
MIDDLE_DROP = 1.0


def build():
    cells = {}
    for led in range(PANELS * STRINGS * LEDS):
        panel, k = divmod(led, STRINGS * LEDS)
        string, row = divmod(k, LEDS)
        x = (PANELS - 1 - panel) * STRINGS + (STRINGS - 1 - string)
        y = int(ROW_PITCH * row + (MIDDLE_DROP if panel == 1 else 0) + 0.5)
        if (x, y) in cells:
            raise SystemExit(f"LEDs {cells[(x, y)]} and {led} both land on cell {x},{y}")
        cells[(x, y)] = led
    return cells


def render(cells):
    height = max(y for _, y in cells) + 1
    grid = [cells.get((x, y), -1) for y in range(height) for x in range(WIDTH)]
    # compact: WLED 16 scans the raw file for the exact bytes "map":[
    text = json.dumps({"n": "curtain", "width": WIDTH, "height": height, "map": grid}, separators=(",", ":"))
    return text, f"{WIDTH} x {height}, {len(cells)} of {len(grid)} cells mapped"


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
