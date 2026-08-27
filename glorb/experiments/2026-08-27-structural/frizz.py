"""Frizzles: fit blur/speed at bri 255 on the fork's sparkle shape (peak, lit count, current)."""
import json, sys, time, threading, math, wledlab
R, T = "10.27.4.160", "10.27.4.158"


def rgb(c):
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def shape(frames):
    lit, peak, hist = [], [], [0] * 5
    for _, leds in frames[::2]:
        v = [max(rgb(c)) if isinstance(c, str) else max(c[:3]) for c in leds]
        l = [x for x in v if x > 12]; lit.append(len(l)); peak.append(max(v))
        for x in l:
            hist[min(4, x * 5 // 256)] += 1
    t = sum(hist) or 1
    return dict(lit=sum(lit) / len(lit), peak=sum(peak) / len(peak), hist=[round(h * 100 / t) for h in hist],
                activity=wledlab.activity(frames), fast=wledlab.fast_share(frames))


def pwr(ip, n=16, dt=0.5):
    v = []
    for _ in range(n):
        v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(v) / len(v)


def capture_both(seconds):
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); return res["ref"], res["tgt"]


def run(ps, seg):
    for ip in (R, T):
        wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": ps})
    time.sleep(1); wledlab.post(T, "/json/state", {"seg": [dict(id=0, **seg)]}); time.sleep(2)
    fr, ft = capture_both(30); time.sleep(3)
    a, b = shape(fr), shape(ft); pa, pb = pwr(R), pwr(T)
    score = abs(math.log(b["peak"] / a["peak"])) + abs(math.log(b["lit"] / a["lit"])) + abs(math.log(pb / pa)) + abs(math.log(b["activity"] / a["activity"]))
    print(f"p{ps} {seg}: ref {a} pwr {pa:.0f} | tgt {b} pwr {pb:.0f} | score {score:.2f}", flush=True)
    return score


plan = json.loads(sys.argv[1])  # {"7": [{...}, ...], "9": [...]}
best = {}
for ps, cands in plan.items():
    res = {json.dumps(c): run(int(ps), c) for c in cands}
    best[ps] = min(res, key=res.get); print("BEST", ps, best[ps], res[best[ps]], flush=True)
for ip in (R, T):
    wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
print("FRIZZ DONE", flush=True)
