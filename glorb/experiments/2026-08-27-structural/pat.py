"""Pattern-layer search for Hiphotic presets: seg0 candidates scored on the fork's structure (contrast, blob size, motion)."""
import json, sys, time, threading, wledlab
sys.path.insert(0, ".")
from structural import feats
from hipsim import H, grids
R, T = "10.27.4.160", "10.27.4.158"
S = "."


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


def pwr(ip, n=24, dt=0.5):
    v = []
    for _ in range(n): v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(v) / len(v)


def capture_both(seconds):
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); return res["ref"], res["tgt"]


for slot in (12, 13):
    print(f"palette{slot}:", wledlab.upload(T, f"/palette{slot}.json", f"{S}/palette{slot}.json"), flush=True)
time.sleep(2)
plan = json.loads(sys.argv[1])
for ps, cands in plan.items():
    single = any("pal" in s and s.get("pal", 0) != 3 and s.get("fx") in (180, 146) and "col" not in s for s in cands.values())
    for name, seg in cands.items():
        for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(ps)})
        time.sleep(1); over = {"seg": [dict(id=0, **seg)]}
        if single: over["seg"].append({"id": 1, "stop": 0})  # single-segment candidate: drop the colour layer
        wledlab.post(T, "/json/state", over); time.sleep(2)
        fr, ft = capture_both(60); time.sleep(3)
        fa, fb = feats(fr), feats(ft); ba, bb = blob(fr), blob(ft); pa, pb = pwr(R), pwr(T)
        print(f"p{ps} {name} {seg}: pwr {pa:.0f}/{pb:.0f} | mean {fa['mean']}/{fb['mean']} sstd {fa['sstd']}/{fb['sstd']} tstd {fa['tstd']}/{fb['tstd']} ratio {fa['ratio']}/{fb['ratio']} | blob-len {ba[0]}/{bb[0]} black% {ba[1]}/{bb[1]}\n   bands ref {fa['bands']} tgt {fb['bands']}\n   vhist ref {fa['vhist']}\n   vhist tgt {fb['vhist']}", flush=True)
for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
print("PAT DONE", flush=True)
