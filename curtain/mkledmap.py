#!/usr/bin/env python3
"""Generate curtain/ledmap.json: the H70B5 curtain on a 60 x 40 grid in true proportions.

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
# the LEDs end on row 38; 40 rows keep the lightshow fixture's 60 x 40 grid
WIDTH, HEIGHT = PANELS * STRINGS, 40
# vertical LED pitch over string pitch (photo: 1.4-1.6): rows land on 0, 2, 3, 5, 6, ...
ROW_PITCH = 1.5


def build():
    cells = {}
    for led in range(PANELS * STRINGS * LEDS):
        panel, k = divmod(led, STRINGS * LEDS)
        string, row = divmod(k, LEDS)
        x = (PANELS - 1 - panel) * STRINGS + (STRINGS - 1 - string)
        y = int(ROW_PITCH * row + 0.5)
        if y >= HEIGHT or (x, y) in cells:
            raise SystemExit(f"LED {led} on cell {x},{y}: outside the grid or taken")
        cells[(x, y)] = led
    return cells


def render(cells):
    grid = [cells.get((x, y), -1) for y in range(HEIGHT) for x in range(WIDTH)]
    # compact: WLED 16 scans the raw file for the exact bytes "map":[
    text = json.dumps({"n": "curtain", "width": WIDTH, "height": HEIGHT, "map": grid}, separators=(",", ":"))
    return text, f"{WIDTH} x {HEIGHT}, {len(cells)} of {len(grid)} cells mapped"


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
