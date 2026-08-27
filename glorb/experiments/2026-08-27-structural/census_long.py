"""Long hue census (>= 3 colour cycles) for the composite/Black Hole presets, optional seg overrides on the target."""
import json, sys, time, wledlab
R, T = "10.27.4.160", "10.27.4.158"
plan = json.loads(sys.argv[1])  # {"2": {"seg": [{"id":0,"col":[[150,150,150],[255,255,255],[255,255,255]]}]}, "12": {}}
seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 100


def pwr(ip, n=40, dt=0.5):
    v = []
    for _ in range(n):
        v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(v) / len(v)


for ps, over in plan.items():
    ps = int(ps)
    for ip in (R, T):
        wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": ps, "seg": [{"id": 0, "frz": False}]})
    if over:
        time.sleep(1); wledlab.post(T, "/json/state", over)
    time.sleep(1.5)
    fr, ft = None, None
    import threading
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); fr, ft = res["ref"], res["tgt"]; time.sleep(3)
    json.dump({"ref": fr, "tgt": ft, "over": over}, open(f"captures/census-p{ps}.json", "w"))
    a, b = wledlab.metrics(fr), wledlab.metrics(ft)
    pa, pb = pwr(R), pwr(T)
    print(f"p{ps:>2} {over}: pwr {pa:.0f}/{pb:.0f} ratio {pb / pa:.2f} | act {a['activity']:.3f}/{b['activity']:.3f} | fast {a['fast_share']:.3f}/{b['fast_share']:.3f} | sat {a['sat_mean']:.2f}/{b['sat_mean']:.2f} | bri {a['bri_mean']:.0f}/{b['bri_mean']:.0f}", flush=True)
    print(f"      hue% ref {a['hue_share']}\n      hue% tgt {b['hue_share']}\n      hueV ref {a['hue_v']}\n      hueV tgt {b['hue_v']}", flush=True)
print("CENSUS DONE", flush=True)
for ip in (R, T):
    wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
