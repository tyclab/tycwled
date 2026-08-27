import json, sys, time, wledlab
R, T = "10.27.4.160", "10.27.4.158"
presets = [int(x) for x in sys.argv[1:]] or [1, 3, 4, 5, 2, 14, 12, 13, 7, 9, 10, 11]


def pwr(ip, n=20, dt=0.5):
    v = []
    for _ in range(n):
        v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(v) / len(v)


for ps in presets:
    fr, ft = wledlab.simultaneous(R, T, 40, preset=ps); time.sleep(3)
    json.dump({"ref": fr, "tgt": ft}, open(f"captures/colour-p{ps}.json", "w"))
    a, b = wledlab.metrics(fr), wledlab.metrics(ft)
    pa, pb = pwr(R), pwr(T)
    print(f"p{ps:>2}: pwr {pa:.0f}/{pb:.0f} ratio {pb / pa:.2f} | activity {a['activity']:.3f}/{b['activity']:.3f} | fast {a['fast_share']:.3f}/{b['fast_share']:.3f} | sat {a['sat_mean']:.2f}/{b['sat_mean']:.2f}", flush=True)
    print(f"      hue% ref {a['hue_share']}\n           tgt {b['hue_share']}\n      hueV ref {a['hue_v']}\n           tgt {b['hue_v']}", flush=True)
print("COLOUR DONE", flush=True)
for ip in (R, T):
    wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
