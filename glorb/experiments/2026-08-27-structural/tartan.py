"""Tartan: line grey g + boosted layer palette k, scored on the fork's crossing colours (hueV per bin, at-255 share, current)."""
import json, sys, time, threading, wledlab
R, T = "10.27.4.160", "10.27.4.158"
S = "."
def rgb(c): return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
def vhist(frames):
    hist = [0] * 10; tot = 0; clip = 0
    for _, leds in frames[::3]:
        for c in leds:
            m = max(rgb(c))
            if m > 12: hist[min(9, m * 10 // 256)] += 1; tot += 1; clip += (m >= 254)
    return [round(h * 100 / tot) for h in hist], round(clip * 100 / tot)
def pwr(ip, n=24, dt=0.5):
    v = []
    for _ in range(n): v.append(wledlab.get(ip, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(v) / len(v)
def capture_both(seconds):
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", wledlab.live(R, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", wledlab.live(T, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join(); return res["ref"], res["tgt"]
for slot in range(14, 20):
    print(f"palette{slot}:", wledlab.upload(T, f"/palette{slot}.json", f"{S}/palette{slot}.json"), flush=True)
time.sleep(2)
plan = json.loads(sys.argv[1])
for ps, cands in plan.items():
    for name, (g, pal) in cands.items():
        for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(ps)})
        time.sleep(1); wledlab.post(T, "/json/state", {"seg": [{"id": 0, "col": [[g, g, g], [g, g, g], [g, g, g]]}, {"id": 1, "pal": pal}]}); time.sleep(2)
        fr, ft = capture_both(70); time.sleep(3)
        a, b = wledlab.metrics(fr), wledlab.metrics(ft); pa, pb = pwr(R), pwr(T)
        print(f"p{ps} {name} g={g} pal={pal}: pwr {pa:.0f}/{pb:.0f} ratio {pb/pa:.2f} | vhist ref {vhist(fr)} tgt {vhist(ft)}\n   hue% ref {a['hue_share']}\n   hue% tgt {b['hue_share']}\n   hueV ref {a['hue_v']}\n   hueV tgt {b['hue_v']}", flush=True)
for ip in (R, T): wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})
print("TARTAN DONE", flush=True)
