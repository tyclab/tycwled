"""Offline Black Hole model: integer-exact FastLED/0.14 arithmetic on a 20x6 buffer.

Scores lit-cell count and mean V the same way wledlab's structural_stats does, so a
hypothesis can be tested against the measured lamp numbers without flashing anything.
"""
import json

W, H = 20, 6

def sin8(theta):
    tbl = [0, 49, 49, 41, 90, 27, 117, 10]
    theta &= 0xFF
    offset = theta
    if theta & 0x40: offset = (255 - offset) & 0xFF
    offset &= 0x3F
    sec = offset & 0x0F
    if theta & 0x40: sec += 1
    s = offset >> 4
    b, m16 = tbl[s * 2], tbl[s * 2 + 1]
    y = (((m16 * sec) >> 4) + b) & 0xFF
    if y >= 128: y -= 256
    if theta & 0x80: y = -y
    return (y + 128) & 0xFF

def scale8(i, s):   return ((i * (s + 1)) >> 8) & 0xFF
def nscale8(c, s):  return tuple(((v * (s + 1)) >> 8) & 0xFF for v in c)
def qadd(c1, c2):   return tuple(min(255, a + b) for a, b in zip(c1, c2))

def beat8(ms, bpm):
    bpm88 = bpm << 8 if bpm < 256 else bpm
    return ((ms * bpm88 * 280) >> 24) & 0xFF

def beatsin8(ms, bpm, lo, hi, phase=0):
    return (lo + scale8(sin8(beat8(ms, bpm) + phase), (hi - lo) & 0xFF)) & 0xFF

def load16(stops):
    """FastLED loadDynamicGradientPalette -> 16 slots."""
    ent = []
    for k in range(16):
        idx = k * 17
        prev = stops[0]
        for s in stops:
            if s[0] <= idx: prev = s
            else: break
        nxt = next((s for s in stops if s[0] > idx), stops[-1])
        span = nxt[0] - prev[0]
        f = 0 if span == 0 else ((idx - prev[0]) * 255) // span
        ent.append(tuple(prev[1 + c] + (((nxt[1 + c] - prev[1 + c]) * f) >> 8) for c in range(3)))
    return ent

def from_palette(ent, i, bri=255):
    hi4, lo4 = (i >> 4) & 15, i & 15
    c1, c2 = ent[hi4], ent[(hi4 + 1) & 15]
    f2 = (lo4 << 4) & 0xFF
    c = tuple(((a * (255 - f2)) >> 8) + ((b * f2) >> 8) for a, b in zip(c1, c2))
    return nscale8(c, bri) if bri < 255 else c

def blur_pass(buf, amount):
    keep, seep = (255 - amount) & 0xFF, amount >> 1
    for y in range(H):
        carry = (0, 0, 0)
        for x in range(W):
            cur = buf[y][x]
            part = nscale8(cur, seep)
            out = qadd(nscale8(cur, keep), carry)
            if x: buf[y][x - 1] = qadd(buf[y][x - 1], part)
            buf[y][x] = out
            carry = part
    for x in range(W):
        carry = (0, 0, 0)
        for y in range(H):
            cur = buf[y][x]
            part = nscale8(cur, seep)
            out = qadd(nscale8(cur, keep), carry)
            if y: buf[y - 1][x] = qadd(buf[y - 1][x], part)
            buf[y][x] = out
            carry = part

def run(stops, sx, ix, c1, c2, frames=900, dt=23, blur=32, count_law=lambda c: (c >> 6) + 2,
        fade_law=lambda c: c >> 4, phase_as_timebase=False):
    ent = load16(stops)
    buf = [[(0, 0, 0)] * W for _ in range(H)]
    lits, means = [], []
    for f in range(frames):
        ms = 100000 + f * dt
        for y in range(H):
            for x in range(W):
                buf[y][x] = nscale8(buf[y][x], (255 - fade_law(c2)) & 0xFF)
        t8 = (ms >> 7) & 0xFFFFFFFF
        n = count_law(c1)
        for i in range(n):
            xph = (i * ((t8 - 128) & 0xFF)) & 0xFF
            yph = ((192 if i & 1 else 64) + i * t8) & 0xFF
            if phase_as_timebase:
                xm, ym = ms - xph, ms - yph
                x = beatsin8(xm, (sx >> 5) + 1, W // 2, (W * 5) // 2 - 1)
                y = beatsin8(ym, (ix >> 4) + 1, 1, H - 2)
            else:
                x = beatsin8(ms, (sx >> 5) + 1, W // 2, (W * 5) // 2 - 1, xph)
                y = beatsin8(ms, (ix >> 4) + 1, 1, H - 2, yph)
            col = from_palette(ent, (i * 63) & 0xFF)
            xx, yy = x % W, min(y, H - 1)
            buf[yy][xx] = qadd(buf[yy][xx], col)
        blur_pass(buf, blur)
        if f > 200:  # let the loop reach steady state
            vs = [max(buf[y][x]) / 255 for y in range(H) for x in range(W)]
            lits.append(sum(1 for v in vs if v > 0.05))
            means.append(sum(v for v in vs if v > 0.05) / max(1, sum(1 for v in vs if v > 0.05)))
    return sum(lits) / len(lits), sum(means) / len(means)

PALX = json.load(open("/home/tycorc/git/tyclab/tycwled/glorb/factory-0.14.4-GLORB.1.3/palx.json"))
SUNSET = [tuple(s) for s in PALX["palettes"]["13"]]
TERTIARY = [tuple(s) for s in PALX["palettes"]["34"]]

if __name__ == "__main__":
    print("baseline (as implemented):")
    for name, stops, sx, ix, c1, c2 in (("p11 Sunset", SUNSET, 210, 50, 40, 20),
                                        ("p10 Tertiary", TERTIARY, 136, 168, 220, 92)):
        lit, mean = run(stops, sx, ix, c1, c2)
        print(f"  {name:<14} lit {lit:6.2f}  meanV {mean:.3f}")

def sweep():
    targets = {"p11": (20.16, 0.247), "p10": (36.93, 0.252)}
    cases = {
        "as implemented (blur32 rows+cols)": dict(blur=32),
        "blur 16":                            dict(blur=16),
        "blur 8":                             dict(blur=8),
        "no blur":                            dict(blur=0),
        "count (c1>>6)+1":                    dict(blur=32, count_law=lambda c: (c >> 6) + 1),
        "count (c1>>7)+2":                    dict(blur=32, count_law=lambda c: (c >> 7) + 2),
        "fade c2>>3":                         dict(blur=32, fade_law=lambda c: c >> 3),
        "fade c2>>2":                         dict(blur=32, fade_law=lambda c: c >> 2),
        "fade c2 raw":                        dict(blur=32, fade_law=lambda c: c),
    }
    print(f"{'case':<36} {'p11 lit':>8} {'p11 V':>7} {'p10 lit':>8} {'p10 V':>7}   verdict")
    print(f"{'FORK (measured)':<36} {20.16:8.2f} {0.247:7.3f} {36.93:8.2f} {0.252:7.3f}")
    for name, kw in cases.items():
        a = run(SUNSET, 210, 50, 40, 20, **kw)
        b = run(TERTIARY, 136, 168, 220, 92, **kw)
        ra, rb = a[0] / targets["p11"][0], b[0] / targets["p10"][0]
        ok = "<-- both within 15%" if 0.85 <= ra <= 1.15 and 0.85 <= rb <= 1.15 else f"lit x{ra:.2f}/x{rb:.2f}"
        print(f"{name:<36} {a[0]:8.2f} {a[1]:7.3f} {b[0]:8.2f} {b[1]:7.3f}   {ok}")
