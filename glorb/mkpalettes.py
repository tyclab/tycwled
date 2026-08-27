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
0.14's scale8(i,240)). A layer can be fitted over the index span the fork
actually visits, with the fork's dwell (`flat` or `sine`) and a brightness
boost where the fork adds two line sets (Tartan). `plain` keeps
the factory stops (Frizzles) or the first part of them (Black Hole, whose
fork Intensity slider limits the star colours to that range).
16's built-in palettes are re-encoded for its gamma (palettes.cpp header), so
with `light.gc` off every preset uses one of these custom palettes.
`--check` verifies the committed files instead of writing them (make lint);
`--report` prints the residual hue/sat/val error of each mirrored palette.
"""
import colorsys
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PALX = os.path.join(HERE, "factory-0.14.4-GLORB.1.3", "palx.json")
OUT = os.path.join(HERE, "wled16-port")
MAX_STOPS = 18
# slot -> (factory palette id, mode); custom palette ID on the lamp = 200 - slot
PLAN = {
    0: (18, "colorwaves"),          # Analogous   — Colorwaves p1 (fx 67: index 0..127, NOWRAP remap)
    1: (13, "colorwaves"),          # Sunset      — Colorwaves p3
    2: (51, "layer", "flat"),       # Atlantica   — Running p4 colour layer (fx 65: LINEARBLEND, no remap)
    3: (18, "layer", "flat"),       # Analogous   — Running p5 colour layer
    4: (34, "layer", "sine"),       # Tertiary    — Hiphotic p2 colour layer
    5: (35, "layer", "flat", (112, 224)),  # Fire — Hiphotic p14 colour layer; the fork only visits indices 112..224 (hue census: 88 % red, 12 % orange, no yellow-white; flat dwell over that span predicts 88 %)
    6: (59, "layer", "sine"),       # Fairy Reaf  — Tartan p12 colour layer
    7: (18, "plain"),               # Analogous   — Frizzles p7
    8: (35, "plain"),               # Fire        — Frizzles p9
    9: (34, "layer", "sine", (0, 220)),  # Tertiary — Black Hole p10 colour layer over the fork's Intensity range 0..220 (its stars mix colours and drift through the palette)
    10: (13, "plain", 40),          # Sunset      — Black Hole p11: first 40/255 (red/orange only, measured hue max 20 deg)
    11: (18, "layer", "sine", (0, 255), 1.4),  # Analogous — Tartan p13 colour layer: sine dwell, and x1.4 clipped because the fork adds its two line sets (crossings reach clip(2*colour); k=2 measured +30 % too bright, 1.7 +20 %, 1.4 on the fork's per-hue brightness)
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


def fork_trajectory(stops, span=(0, 255), boost=1.0):
    """0.14 color_from_palette without wrap: scale8(index, 240) = (i*241)>>8, then LINEARBLEND.
    span restricts the sweep to the part of the palette the fork actually visits (measured on the
    lamp: Fire never leaves 112..224 -- dark red to orange, no black, no yellow-white), resampled to 256 steps.
    boost scales and clips the colours (Tartan adds two line sets, so its pixels sit between C and clip(2C))."""
    ent = load16(stops)
    lo, hi = span
    return [[min(255, round(boost * v)) for v in cfp014(ent, ((lo + (hi - lo) * t // 255) * 241) >> 8)] for t in range(256)]


def fork_phase(p, dwell):
    """Fork palette index (0..255) visited while the port's linear up-sweep is at index p (0..127).
    flat: the fork's index also moves linearly (Running). sine: the fork's index is sin8-driven
    (Hiphotic, Tartan) and lingers at both palette ends, so the port's uniform time is warped by the
    arcsine law -- the same colour share per palette region as the fork (measured dwell per eighth
    of the palette on the factory lamp: ends 17-29 %, middle 8-12 %)."""
    u = (p + 0.5) / 128
    t = 127.5 * (1 - math.cos(math.pi * u)) if dwell == "sine" else 255 * u
    return min(255, int(t))


def slot_position(p, mode):
    """Index after WLED 16's blend remap: Colorwaves uses LINEARBLEND_NOWRAP (x240/256); the Palette effect LINEARBLEND (none)."""
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


def mirror(stops, mode, dwell="flat", span=(0, 255), boost=1.0):
    """8 slot colours fitted to the fork trajectory as the port's effect reads them, mirrored for the down sweep."""
    T = fork_trajectory(stops, span, boost)
    A, b = [], []
    for p in range(128):
        q = slot_position(p, mode); hi, lo = q >> 4, q & 15; w = (lo << 4) / 256
        row = [0.0] * 8; row[hi] += 1 - w; row[min(hi + 1, 7)] += w; A.append(row); b.append(T[fork_phase(p, dwell)])
    # the sweep's turning points are the colours the eye anchors on: weight them in the fit
    idx = list(range(128)) + [0] * 16 + [127] * 16
    S = [[max(0, min(255, round(v))) for v in solve([A[i] for i in idx], [b[i][c] for i in idx])] for c in range(3)]
    up = [[16 * k, S[0][k], S[1][k], S[2][k]] for k in range(8)]
    down = [[128 + 16 * j] + up[7 - j][1:] for j in range(8)]
    return up + down + [[255] + up[0][1:]]


def residual(stops, new, mode, dwell="flat", span=(0, 255), boost=1.0):
    """Worst hue/sat/val deviation of the port (exact 16 arithmetic) from the fork over one sweep."""
    F = fork_trajectory(stops, span, boost); ent = load16(new); worst = [0, 0, 0]
    for p in range(128):
        f, q = F[fork_phase(p, dwell)], cfp16(ent, p, mode == "colorwaves")
        hf, sf, vf = colorsys.rgb_to_hsv(*[x / 255 for x in f]); hp, sp, vp = colorsys.rgb_to_hsv(*[x / 255 for x in q])
        dh = min(abs(hf - hp), 1 - abs(hf - hp)) * 360 if sf > 0.05 and sp > 0.05 else 0
        worst = [max(worst[0], dh), max(worst[1], abs(sf - sp)), max(worst[2], abs(vf - vp))]
    return worst


def head(stops, upto):
    """The first `upto`/255 of the fork palette stretched over 0..255, as the fork's Black Hole
    Intensity slider limits the star colours: slot k of the port = fork colour at index k*upto/16."""
    ent = load16(stops)
    return [[min(255, 16 * k)] + cfp014(ent, k * upto // 16) for k in range(17)]


def build(stops, mode, arg=None, span=(0, 255), boost=1.0):
    if mode == "plain":
        if arg is not None:
            return head(stops, arg)
        assert len(stops) <= MAX_STOPS, "plain palette exceeds WLED's 18 stops"
        return stops
    return mirror(stops, mode, arg or "flat", span, boost)


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
    for slot, plan in PLAN.items():
        pid, mode = plan[:2]; arg = plan[2] if len(plan) > 2 else None; span = plan[3] if len(plan) > 3 else (0, 255); boost = plan[4] if len(plan) > 4 else 1.0
        stops = palx["palettes"][str(pid)]
        new = build(stops, mode, arg, span, boost)
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
            h, s, v = residual(stops, new, mode, arg or "flat", span, boost); extra = f" | residual vs fork: hue {h:.1f} deg, sat {s:.2f}, val {v:.2f}"
        print(f"{name}: ID {200 - slot} {palx['names'][pid]} {mode} {len(flat) // 4} stops {'ok' if args.check else 'written'}{extra}")


if __name__ == "__main__":
    main()
