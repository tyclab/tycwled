#!/usr/bin/env python3
"""Generate curtain/meteor.gif: the Govee H70B5 "Music: Meteor shower" look for WLED's Image effect.

A diagonal front sweeps the 68 x 42 canvas left to right and lights a lattice of blue dots
behind a white-cyan edge; the lattice then winks out while cyan and white sparkles drift
and fade, and the loop restarts. The pace is baked into the frames (120 ms, ~23 s per loop)
because the Image effect's speed slider moves it by a third at most. Needs Pillow.
`--check` verifies the committed file instead of writing it.
"""
import os
import random
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "meteor.gif")
W, H = 68, 42
DELAY_MS = 120
SWEEP, DISSOLVE, FADE = 80, 80, 30          # frames per phase
BLUE, CYAN, WHITE = (0, 40, 255), (0, 200, 255), (210, 235, 255)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(c, k):
    return tuple(int(v * k) for v in c)


def lattice(x, y):
    return x % 2 == 0 and (x // 2 + y) % 3 == 0


def frames():
    rnd = random.Random(7)
    out = []
    # The front crosses the canvas diagonally; dots just behind it are white, then cyan, then blue.
    for f in range(SWEEP):
        img = Image.new("RGB", (W, H))
        px = img.load()
        front = -H * 0.5 + (W + H * 0.5 + 6) * f / (SWEEP - 1)
        for y in range(H):
            for x in range(W):
                if not lattice(x, y):
                    continue
                d = front - (x - 0.5 * y)
                if d < 0:
                    continue
                if d < 2:
                    c = WHITE
                elif d < 5:
                    c = mix(CYAN, BLUE, (d - 2) / 3)
                else:
                    c = scale(BLUE, max(0.45, 1 - (d - 5) / 90))
                px[x, y] = c
        out.append(img)
    # Lattice dots wink out one by one (a cyan flash each) while sparkles are born and fade.
    alive = {(x, y): rnd.randint(0, DISSOLVE - 8)
             for y in range(H) for x in range(W) if lattice(x, y)}
    sparks = {}
    for f in range(DISSOLVE + FADE):
        img = Image.new("RGB", (W, H))
        px = img.load()
        for (x, y), t0 in alive.items():
            if f < t0:
                px[x, y] = scale(BLUE, 0.6)
            elif f < t0 + 2:
                px[x, y] = CYAN
        births = 6 if f < DISSOLVE else max(0, int(6 * (1 - (f - DISSOLVE) / FADE)))
        for _ in range(births):
            sparks[(rnd.randrange(W), rnd.randrange(H))] = (f, rnd.choice([WHITE, CYAN, CYAN, BLUE]))
        for (x, y), (t0, c) in list(sparks.items()):
            age, life = f - t0, 10
            if age > life:
                del sparks[(x, y)]
                continue
            px[x, y] = scale(c, 1.0 if age < 2 else 1 - (age - 2) / (life - 2))
        out.append(img)
    return out


def render(path):
    q = [fr.quantize(colors=32, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
         for fr in frames()]
    q[0].save(path, format="GIF", save_all=True, append_images=q[1:], duration=DELAY_MS,
              loop=0, disposal=1, optimize=True)


def main():
    if "--check" in sys.argv:
        tmp = OUT + ".check"
        render(tmp)
        try:
            same = open(tmp, "rb").read() == open(OUT, "rb").read()
        finally:
            os.unlink(tmp)
        print("meteor.gif ok" if same else "meteor.gif differs from its generator output")
        return 0 if same else 1
    render(OUT)
    print(f"{OUT}: {os.path.getsize(OUT)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
