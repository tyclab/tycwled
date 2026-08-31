"""Pattern-layer search for Hiphotic presets: seg0 candidates scored on the fork's structure (contrast, blob size, motion).

    PYTHONPATH=. python3 glorb/experiments/2026-08-27-structural/pat.py '{"14": {"name": {seg0 fields...}, ...}}'

A candidate with "single": true is applied as one segment (the colour layer, seg 1, is dropped); every other
candidate keeps the preset's seg 1. Palettes 12-15 are uploaded from this directory first (see PALETTES).
Every swept parameter is read back from /json/state and must match exactly -- a clamped slider (c3 > 31)
or an ignored key aborts the run instead of silently scoring a different configuration.
An optional second argument N runs every candidate N times so the score spread (the error bar) is visible;
a ranking whose gap lies inside the replicate spread is noise."""
import json, os, sys, threading, time, wledlab
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from structural import feats, pwr_both
from hipsim import H, grids
R, T = "10.27.4.160", "10.27.4.158"
S = os.path.dirname(os.path.abspath(__file__))
PALETTES = {12: "pattern-steep-188.json", 13: "pattern-linear-187.json", 14: "fire-span-112-224-plain-186.json", 15: "fire-span-64-224-plain-185.json"}
SECONDS = 100  # >= 3 colour cycles; 10-40 s windows swing +-25 %


def blob(frames):
    """spatial autocorrelation length along rows (cells where autocorr drops below 0.3) and black share"""
    gr = grids(frames); acs = []; black = 0; n = 0
    for _, G in gr[::10]:
        for y in range(H):
            row = [v for v in G[y] if v is not None]
            if len(row) < 8: continue
            m = sum(row) / len(row); d = [v - m for v in row]; den = sum(x * x for x in d) or 1
            ac = [sum(d[i] * d[i + l] for i in range(len(d) - l)) / den for l in range(len(d) // 2)]
            acs.append(next((l for l, a in enumerate(ac) if a < 0.3), len(ac)))
            for v in row: n += 1; black += v < 0.05
    return round(sum(acs) / len(acs), 1), round(black * 100 / n)


def capture_both(seconds):
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); return res["ref"], res["tgt"]


def main(plan, replicates=1):
    for slot, fname in PALETTES.items():
        wledlab.upload(T, f"/palette{slot}.json", os.path.join(S, fname))
        have = wledlab.readback(T, f"/palette{slot}.json"); want = open(os.path.join(S, fname), "rb").read()
        if have != want:
            raise SystemExit(f"palette{slot}.json readback differs from {fname}")
        print(f"palette{slot}: {fname} ok", flush=True)
    time.sleep(2)
    try:
        for ps, cands in plan.items():
            for name, seg in [(f"{n}#{r + 1}" if replicates > 1 else n, s) for n, s in cands.items() for r in range(replicates)]:
                seg = dict(seg); single = seg.pop("single", False)
                for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(ps)})
                time.sleep(1); over = {"seg": [dict(id=0, **seg)]}
                if single: over["seg"].append({"id": 1, "stop": 0})  # single-segment candidate: drop the colour layer
                wledlab.post(T, "/json/state", over); time.sleep(2)
                rb = wledlab.get(T, "/json/state")["seg"][0]
                for key, val in seg.items():
                    if rb.get(key) != val:
                        raise SystemExit(f"{name}: {key} readback {rb.get(key)!r} != requested {val!r} -- clamped or ignored; fix the candidate")
                fr, ft = capture_both(SECONDS); time.sleep(3)
                fa, fb = feats(fr), feats(ft); ba, bb = blob(fr), blob(ft); pa, pb = pwr_both(R, T)
                print(f"p{ps} {name}{' [single]' if single else ''} {seg}: pwr {pa:.0f}/{pb:.0f} | mean {fa['mean']}/{fb['mean']} sstd {fa['sstd']}/{fb['sstd']} tstd {fa['tstd']}/{fb['tstd']} ratio {fa['ratio']}/{fb['ratio']} | blob-len {ba[0]}/{bb[0]} black% {ba[1]}/{bb[1]}\n   bands ref {fa['bands']} tgt {fb['bands']}\n   vhist ref {fa['vhist']}\n   vhist tgt {fb['vhist']}", flush=True)
        print("PAT DONE", flush=True)
    finally:
        for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})


if __name__ == "__main__":
    main(json.loads(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1)
