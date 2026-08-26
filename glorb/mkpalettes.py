#!/usr/bin/env python3
"""Generate glorb/wled16-port/paletteN.json from the factory /json/palx dump.

WLED 16 built-in palettes are re-encoded for its per-pixel gamma (palettes.cpp
header), so with `light.gc` off the 0.14 look needs the 0.14 stop values as
custom palettes. Modes: `plain` = the factory stops; `mirror` = stops packed
into 0-127 plus the reverse in 128-255 (Colorwaves' 0-127 hue sweep and the
Palette effect's sawtooth both become the fork's full triangle cycle).
WLED caps custom palettes at 18 stops; longer inputs are resampled.
`--check` verifies the committed files instead of writing them (make lint).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PALX = os.path.join(HERE, "factory-0.14.4-GLORB.1.3", "palx.json")
OUT = os.path.join(HERE, "wled16-port")
MAX_STOPS = 18
# slot -> (factory palette id, mode); custom palette ID on the lamp = 200 - slot
PLAN = {
    0: (18, "mirror"),  # Analogous   — Colorwaves p1
    1: (13, "mirror"),  # Sunset      — Colorwaves p3
    2: (51, "mirror"),  # Atlantica   — Running p4 colour layer
    3: (18, "mirror"),  # Analogous   — Running p5 / Tartan p13 colour layer
    4: (34, "mirror"),  # Tertiary    — Hiphotic p2 colour layer
    5: (35, "mirror"),  # Fire        — Hiphotic p14 colour layer
    6: (59, "mirror"),  # Fairy Reaf  — Tartan p12 colour layer
    7: (18, "plain"),   # Analogous   — Frizzles p7
    8: (35, "plain"),   # Fire        — Frizzles p9
    9: (34, "plain"),   # Tertiary    — Black Hole p10
    10: (13, "plain"),  # Sunset      — Black Hole p11
}


def interp(stops, i):
    for (a, *ca), (b, *cb) in zip(stops, stops[1:]):
        if a <= i <= b:
            t = (i - a) / (b - a) if b > a else 0
            return [round(x + (y - x) * t) for x, y in zip(ca, cb)]
    return list(stops[-1][1:])


def resample(stops, n):
    return [[round(255 * k / (n - 1))] + interp(stops, round(255 * k / (n - 1))) for k in range(n)]


def build(stops, mode):
    if mode == "plain":
        return stops if len(stops) <= MAX_STOPS else resample(stops, MAX_STOPS)
    if len(stops) * 2 > MAX_STOPS:
        stops = resample(stops, MAX_STOPS // 2)
    lo = [[i // 2] + c for i, *c in stops]
    hi = [[128 + (255 - i) // 2] + c for i, *c in reversed(stops)]
    return lo + hi


def lint(flat, name):
    idx = flat[0::4]
    assert len(flat) % 4 == 0, f"{name}: length not a multiple of 4"
    assert 2 <= len(idx) <= MAX_STOPS, f"{name}: {len(idx)} stops (WLED max {MAX_STOPS})"
    assert idx[0] == 0 and idx[-1] == 255, f"{name}: must start at 0 and end at 255 (got {idx[0]}..{idx[-1]})"
    assert idx == sorted(idx), f"{name}: indices not monotonic"
    assert all(0 <= v <= 255 for v in flat), f"{name}: value out of range"


def main():
    palx = json.load(open(PALX))
    check = "--check" in sys.argv
    for slot, (pid, mode) in PLAN.items():
        stops = palx["palettes"][str(pid)]
        flat = [v for s in build(stops, mode) for v in s]
        name = f"palette{slot}.json"
        lint(flat, name)
        body = json.dumps({"palette": flat}, separators=(",", ":"))
        path = os.path.join(OUT, name)
        if check:
            have = open(path).read().strip()
            assert have == body, f"{name}: committed file differs from generator output (ID {200 - slot}, {palx['names'][pid]} {mode})"
        else:
            open(path, "w").write(body)
        print(f"{name}: ID {200 - slot} {palx['names'][pid]} {mode} {len(flat) // 4} stops {'ok' if check else 'written'}")


if __name__ == "__main__":
    main()
