"""Black Hole: which model of the fork's sliders reproduces its hue census? Runs candidates on the port, 60 s each."""
import json, sys, time, threading, wledlab
R, T = "10.27.4.160", "10.27.4.158"
S = "."


def rgb(c):
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def lit(frames):
    n = [sum(1 for c in leds if max(rgb(c)) > 12) for _, leds in frames[::2]]
    return sum(n) / len(n)


def pwr(ip, n=24, dt=0.5):
    v = []
    for _ in range(n):
        v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
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
    for name, seg in cands.items():
        for ip in (R, T):
            wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(ps)})
        time.sleep(1); wledlab.post(T, "/json/state", {"seg": [dict(id=0, **seg)]}); time.sleep(2)
        fr, ft = capture_both(60); time.sleep(3)
        a, b = wledlab.metrics(fr), wledlab.metrics(ft); pa, pb = pwr(R), pwr(T)
        print(f"p{ps} {name} {seg}: pwr {pa:.0f}/{pb:.0f} lit {lit(fr):.1f}/{lit(ft):.1f} sat {a['sat_mean']:.2f}/{b['sat_mean']:.2f} fast {a['fast_share']:.2f}/{b['fast_share']:.2f}\n   hue% ref {a['hue_share']}\n   hue% tgt {b['hue_share']}\n   hueV ref {a['hue_v']}\n   hueV tgt {b['hue_v']}", flush=True)
for ip in (R, T):
    wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
print("BH DONE", flush=True)
