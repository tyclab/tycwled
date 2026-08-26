#!/usr/bin/env python3
"""Generate glorb/wled16-port/paletteN.json from the factory /json/palx dump.

WLED holds every palette as 16 slots (FastLED CRGBPalette16) and blends
linearly between neighbouring slots. The fork sweeps a palette over index
0..255 (16 slots); stock Colorwaves only sweeps 0..127 and the Palette effect
needs palette+reverse for the fork's triangle cycle, so the port has 8 slots
per direction. Packing the factory stops into 0..127 lets FastLED's loader
round them into neighbouring slots (visible hue steps, up to 64 deg on
Analogous). `colorwaves` and `layer` therefore fit the 8 slot colours by least squares
to the fork's own 16-slot trajectory as the port's effect reads it
(Colorwaves: LINEARBLEND_NOWRAP with WLED 16's 240/256 index remap; the
Palette effect: LINEARBLEND, no remap) and write them at exact slot indices
(0,16,..,240,255 = 17 stops, no loader rounding). All arithmetic mirrors the
C++ (FastLED 16.16 gradient fill, WLED 16 and FastLED 3.6 blend weights,
0.14's scale8(i,240)). `plain` keeps the factory stops (Frizzles/Black Hole
index the palette like the fork does).
16's built-in palettes are re-encoded for its gamma (palettes.cpp header), so
with `light.gc` off every preset uses one of these custom palettes.
`--check` verifies the committed files instead of writing them (make lint);
`--report` prints the residual hue/sat/val error of each mirrored palette.
"""
import colorsys
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PALX = os.path.join(HERE, "factory-0.14.4-GLORB.1.3", "palx.json")
OUT = os.path.join(HERE, "wled16-port")
MAX_STOPS = 18
# slot -> (factory palette id, mode); custom palette ID on the lamp = 200 - slot
PLAN = {
    0: (18, "colorwaves"),  # Analogous   — Colorwaves p1 (fx 67: index 0..127, NOWRAP remap)
    1: (13, "colorwaves"),  # Sunset      — Colorwaves p3
    2: (51, "layer"),       # Atlantica   — Running p4 colour layer (fx 65: LINEARBLEND, no remap)
    3: (18, "layer"),       # Analogous   — Running p5 / Tartan p13 colour layer
    4: (34, "layer"),       # Tertiary    — Hiphotic p2 colour layer
    5: (35, "layer"),       # Fire        — Hiphotic p14 colour layer
    6: (59, "layer"),       # Fairy Reaf  — Tartan p12 colour layer
    7: (18, "plain"),   # Analogous   — Frizzles p7
    8: (35, "plain"),   # Fire        — Frizzles p9
    9: (34, "plain"),   # Tertiary    — Black Hole p10
    10: (13, "plain"),  # Sunset      — Black Hole p11
}


def load16(stops):
    """FastLED loadDynamicGradientPalette + fill_gradient_RGB (16.16 fixed point), 16 slots."""
    ent = [[0, 0, 0]] * 16; count = len(stops); last = -1
    idx0, rgb0 = stops[0][0], stops[0][1:]
    for s in stops[1:]:
        idx1, rgb1 = s[0], s[1:]; a, b = idx0 // 16, idx1 // 16
        if count < 16:
            if a <= last < 15:
                a = last + 1
                if b < a:
                    b = a
            last = b
        div = b - a
        for c in range(3):
            acc = rgb0[c] << 16
            delta = int(((rgb1[c] - rgb0[c]) << 16) / div) if div else 0  # C division truncates toward zero
            for k in range(a, b + 1):
                col = list(ent[k]); col[c] = (acc >> 16) & 255; ent[k] = col; acc += delta
        idx0, rgb0 = idx1, rgb1
        if idx0 >= 255:
            break
    return ent


def cfp16(ent, index, nowrap):
    """WLED 16 colors.cpp ColorFromPalette: NOWRAP remaps index by 240/256; weights lo4/16."""
    if nowrap:
        index = (index * 0xF0) >> 8
    hi, lo = index >> 4, index & 15
    e0, e1 = ent[hi], ent[(hi + 1) % 16]
    f2 = lo << 4; f1 = 256 - f2
    return [(a * f1 + b * f2) >> 8 for a, b in zip(e0, e1)]


def cfp014(ent, index):
    """FastLED 3.6 ColorFromPalette LINEARBLEND with SCALE8_FIXED, as used by 0.14."""
    hi, lo = index >> 4, index & 15
    e0, e1 = ent[hi], ent[(hi + 1) % 16]
    f2 = lo << 4; f1 = 255 - f2
    return [((a * (f1 + 1)) >> 8) + ((b * (f2 + 1)) >> 8) for a, b in zip(e0, e1)]


def fork_trajectory(stops):
    """0.14 color_from_palette without wrap: scale8(index, 240) = (i*241)>>8, then LINEARBLEND."""
    ent = load16(stops)
    return [cfp014(ent, (t * 241) >> 8) for t in range(256)]


def port_index(t):
    """Port palette index for fork phase t: both Colorwaves (0..127) and the Palette effect's up-sweep cover half the range."""
    return t * 127 // 255


def slot_position(t, mode):
    """Index after WLED 16's blend remap: Colorwaves uses LINEARBLEND_NOWRAP (×240/256); the Palette effect LINEARBLEND (none)."""
    p = port_index(t)
    return ((p * 0xF0) >> 8) if mode == "colorwaves" else p


def solve(A, b):
    n = len(A[0])
    M = [[sum(A[t][i] * A[t][j] for t in range(len(A))) for j in range(n)] + [sum(A[t][i] * b[t] for t in range(len(A)))] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i and M[r][i]:
                f = M[r][i] / M[i][i]
                M[r] = [x - f * y for x, y in zip(M[r], M[i])]
    return [M[i][n] / M[i][i] for i in range(n)]


def mirror(stops, mode):
    """8 slot colours fitted to the fork trajectory as the port's effect reads them, mirrored for the down sweep."""
    T = fork_trajectory(stops)
    A = []
    for t in range(256):
        q = slot_position(t, mode); hi, lo = q >> 4, q & 15; w = (lo << 4) / 256
        row = [0.0] * 8; row[hi] += 1 - w; row[min(hi + 1, 7)] += w; A.append(row)
    S = [[max(0, min(255, round(v))) for v in solve(A, [T[t][c] for t in range(256)])] for c in range(3)]
    up = [[16 * k, S[0][k], S[1][k], S[2][k]] for k in range(8)]
    down = [[128 + 16 * j] + up[7 - j][1:] for j in range(8)]
    return up + down + [[255] + up[0][1:]]


def residual(stops, new, mode):
    """Worst hue/sat/val deviation of the port (exact 16 arithmetic) from the fork over one sweep."""
    F = fork_trajectory(stops); ent = load16(new); worst = [0, 0, 0]
    for t in range(256):
        f, p = F[t], cfp16(ent, port_index(t), mode == "colorwaves")
        hf, sf, vf = colorsys.rgb_to_hsv(*[x / 255 for x in f]); hp, sp, vp = colorsys.rgb_to_hsv(*[x / 255 for x in p])
        dh = min(abs(hf - hp), 1 - abs(hf - hp)) * 360 if sf > 0.05 and sp > 0.05 else 0
        worst = [max(worst[0], dh), max(worst[1], abs(sf - sp)), max(worst[2], abs(vf - vp))]
    return worst


def build(stops, mode):
    if mode == "plain":
        assert len(stops) <= MAX_STOPS, "plain palette exceeds WLED's 18 stops"
        return stops
    return mirror(stops, mode)


def lint(flat, name):
    idx = flat[0::4]
    assert len(flat) % 4 == 0, f"{name}: length not a multiple of 4"
    assert 2 <= len(idx) <= MAX_STOPS, f"{name}: {len(idx)} stops (WLED max {MAX_STOPS})"
    assert idx[0] == 0 and idx[-1] == 255, f"{name}: must start at 0 and end at 255 (got {idx[0]}..{idx[-1]})"
    assert idx == sorted(idx), f"{name}: indices not monotonic"
    assert all(0 <= v <= 255 for v in flat), f"{name}: value out of range"


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify committed palette files match the generator (used by make lint)")
    ap.add_argument("--report", action="store_true", help="print residual hue/sat/val error of each mirrored palette vs the fork")
    args = ap.parse_args()
    palx = json.load(open(PALX))
    for slot, (pid, mode) in PLAN.items():
        stops = palx["palettes"][str(pid)]
        new = build(stops, mode)
        flat = [v for s in new for v in s]
        name = f"palette{slot}.json"
        lint(flat, name)
        body = json.dumps({"palette": flat}, separators=(",", ":"))
        path = os.path.join(OUT, name)
        if args.check:
            have = open(path).read().strip()
            assert have == body, f"{name}: committed file differs from generator output (ID {200 - slot}, {palx['names'][pid]} {mode})"
        else:
            open(path, "w").write(body)
        extra = ""
        if args.report and mode != "plain":
            h, s, v = residual(stops, new, mode); extra = f" | residual vs fork: hue {h:.1f} deg, sat {s:.2f}, val {v:.2f}"
        print(f"{name}: ID {200 - slot} {palx['names'][pid]} {mode} {len(flat) // 4} stops {'ok' if args.check else 'written'}{extra}")


if __name__ == "__main__":
    main()
