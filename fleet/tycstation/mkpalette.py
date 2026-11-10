#!/usr/bin/env python3
"""Generate the TycStation palette for the fleet's WLED lamps as custom palette files.

The mark's gradient, blue #5aa2ff to violet #8b6cf0 (at 48 %) to red #ff4a3d, mirrored back to
blue so that effects which run round the palette meet no seam. WLED numbers custom palettes
downward from ID 200 by file slot, so each lamp gets the first slot its own palettes leave free:

- palette0.json (ID 200): the curtain, the couch and the Moon, which have no custom palettes and
  run output gamma 2.8. The stops hold the mark's values as drawn, as the squid GIFs do.
- glorb/palette6.json (ID 194): the GLORBs, whose port holds palettes 0-5 and runs output gamma
  1.0. The stops hold what WLED's 2.8 table makes of the drawn values, so every lamp puts the
  same values on the wire.

`--check` verifies the committed files instead of writing them (make lint).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE, VIOLET, RED = (90, 162, 255), (139, 108, 240), (255, 74, 61)
# Position (0-255) and colour of each stop: out to red at the middle, back to blue at the end.
STOPS = [(0, BLUE), (61, VIOLET), (128, RED), (195, VIOLET), (255, BLUE)]
# WLED 16's output table for gamma 2.8 (colour gamma on).
GAMMA_28 = [int((i / 255) ** 2.8 * 255 + 0.5) for i in range(256)]
# The GLORB port ships palette0.json-palette5.json (glorb/mkpalettes.py PLAN); this one follows them.
GLORB_SLOT = 6
FILES = {
    "palette0.json": lambda c: c,
    os.path.join("glorb", f"palette{GLORB_SLOT}.json"): lambda c: tuple(GAMMA_28[v] for v in c),
}


def render(encode):
    flat = []
    for at, colour in STOPS:
        flat += [at, *encode(colour)]
    # The exact bytes WLED 16 scans: one line, no spaces, as the GLORB palettes are written.
    return json.dumps({"palette": flat}, separators=(",", ":")) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    bad = []
    for name, encode in FILES.items():
        path, want = os.path.join(HERE, name), render(encode)
        if check:
            have = open(path).read() if os.path.exists(path) else None
            print(f"{name}: {'ok' if have == want else 'DIFFERS from the generator'}")
            bad += [] if have == want else [name]
        else:
            with open(path, "w") as f:
                f.write(want)
            print(f"{name}: written")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
