#!/usr/bin/env python3
"""Generate glorb/wled16-port/paletteN.json from the factory /json/palx dump.

The factory presets use six built-in palettes. WLED re-encoded most of its
built-in gradient palettes after 0.14 (they are regenerated from cpt-city
.c3g sources and stored brighter, expecting output gamma to bring them back
down), so the same palette ID no longer holds the same bytes:

    Analogous 18, red channel   fork  3  23  67 142 255
                                WLED 16   38  86 139 196 255

Only Atlantica 51 survives byte-identical -- and Atlantica was the one preset
that matched the factory lamp before this file was rewritten.

So the port cannot use the built-in palettes. It ships the factory stops
verbatim as WLED custom palettes and points the presets at those IDs. No
fitting, no re-encoding, no approximation: the same numbers the fork holds,
rendered by effects decompiled from the fork, under the factory's own gamma.

An earlier revision of this file fitted 8-slot approximations by least squares
because the port was running stock WLED effects that swept the palette
differently. The effects are now exact reimplementations, so the palettes are
taken verbatim and the fitting is gone.

`--check` verifies the committed files instead of writing them (make lint).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PALX = os.path.join(HERE, "factory-0.14.4-GLORB.1.3", "palx.json")
OUT = os.path.join(HERE, "wled16-port")

# WLED custom palettes count downward from this ID: slot 0 is 200, slot 1 is 199, ...
CUSTOM_PALETTE_ID_BASE = 200

# slot -> factory built-in palette ID that the factory presets reference
PLAN = {
    0: 13,  # Sunset      -- Colorwaves p3, Black Hole p11
    1: 18,  # Analogous   -- Colorwaves p1, Running p5, Frizzles p7, Tartan p13
    2: 34,  # Tertiary    -- Hiphotic p2, Black Hole p10
    3: 35,  # Fire        -- Frizzles p9, Hiphotic p14
    4: 51,  # Atlantica   -- Running p4
    5: 59,  # Fairy Reaf  -- Tartan p12
}


def custom_id(slot):
    return CUSTOM_PALETTE_ID_BASE - slot


def factory_palettes():
    d = json.load(open(PALX))
    return d["palettes"], d["names"]


def build():
    """slot -> (filename, file body, factory palette id, name)"""
    palettes, names = factory_palettes()
    out = {}
    for slot, pid in sorted(PLAN.items()):
        stops = palettes[str(pid)]
        flat = [v for stop in stops for v in stop]
        if flat[0] != 0 or flat[-4] != 255:
            raise SystemExit(f"palette {pid}: stops must span index 0..255, got {flat[0]}..{flat[-4]}")
        if len(stops) > 18:
            raise SystemExit(f"palette {pid}: {len(stops)} stops, WLED accepts at most 18")
        if any(not 0 <= v <= 255 for v in flat):
            raise SystemExit(f"palette {pid}: channel/index outside 0..255")
        out[slot] = (f"palette{slot}.json", {"palette": flat}, pid, names[pid])
    return out


def main():
    check = "--check" in sys.argv
    bad = []
    for slot, (fn, body, pid, name) in sorted(build().items()):
        path = os.path.join(OUT, fn)
        text = json.dumps(body, separators=(",", ":"))
        n = len(body["palette"]) // 4
        if check:
            have = open(path).read() if os.path.exists(path) else None
            ok = have == text
            bad += [] if ok else [fn]
            print(f"{fn}: ID {custom_id(slot)} {name} (factory {pid}) {n} stops {'ok' if ok else 'STALE -- rerun mkpalettes.py'}")
        else:
            open(path, "w").write(text)
            print(f"{fn}: ID {custom_id(slot)} {name} (factory {pid}) {n} stops written")
    stale = [f for f in os.listdir(OUT) if f.startswith("palette") and f.endswith(".json")
             and f not in {v[0] for v in build().values()}]
    if stale:
        print("unexpected palette files (delete them):", ", ".join(sorted(stale)))
        bad += stale
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
