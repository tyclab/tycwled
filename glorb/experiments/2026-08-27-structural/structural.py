"""Structural comparison of every preset: brightness histogram, global/spatial swell ratio, spectrum bands,
per-frame hue spread, hue census, breathing waveform. 100 s per preset, both lamps at once.

    PYTHONPATH=. python3 glorb/experiments/2026-08-27-structural/structural.py [preset ...]
    PYTHONPATH=. python3 glorb/experiments/2026-08-27-structural/structural.py --offline [preset ...]

--offline re-scores the saved captures/struct-pN.json without touching the lamps (no current reading).
Importable without side effects (pat.py uses feats/pwr_both)."""
import json, math, os, sys, time, wledlab
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hipsim import W, H, grids
R, T = "10.27.4.160", "10.27.4.158"
fs = 10
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
CAP = os.path.join(ROOT, "captures")


def feats(frames):
    gr = grids(frames); t0 = gr[0][0]
    cells = [(y, x) for y in range(H) for x in range(W) if gr[0][1][y][x] is not None and max(G[y][x] for _, G in gr) > 0.05]
    n = int((gr[-1][0] - t0) * fs); out = {c: [] for c in cells}; j = 0; mean = []
    for k in range(n):
        t = t0 + k / fs
        while j + 1 < len(gr) and gr[j + 1][0] <= t:
            j += 1
        G = gr[j][1]; m = 0
        for c in cells:
            v = G[c[0]][c[1]]; out[c].append(v); m += v
        mean.append(m / len(cells))
    tot = [0] * 5
    cs = [[math.cos(2 * math.pi * k * i / n) for i in range(n)] for k in range(1, n // 2)]
    sn = [[math.sin(2 * math.pi * k * i / n) for i in range(n)] for k in range(1, n // 2)]
    for c, s in out.items():
        m = sum(s) / n; d = [x - m for x in s]
        for k in range(1, n // 2):
            f = k * fs / n; re = sum(a * b for a, b in zip(d, cs[k - 1])); im = sum(a * b for a, b in zip(d, sn[k - 1])); p = re * re + im * im
            tot[0 if f < 0.1 else 1 if f < 0.3 else 2 if f < 1 else 3 if f < 3 else 4] += p
    Tt = sum(tot) or 1; bands = [round(v / Tt * 100, 1) for v in tot]
    mm = sum(mean) / n; tstd = (sum((x - mm) ** 2 for x in mean) / n) ** 0.5
    sstd = sum((sum((out[c][k] - mean[k]) ** 2 for c in cells) / len(cells)) ** 0.5 for k in range(n)) / n
    hist = [0] * 10
    for c in cells:
        for v in out[c]:
            hist[min(9, int(v * 10))] += 1
    ht = sum(hist)
    g = " ▁▂▃▄▅▆▇█"
    wave = "".join(g[min(8, int(v * 8.99))] for v in mean[::5][:120])
    return dict(bands=bands, ratio=round(sstd / tstd, 2) if tstd else None, tstd=round(tstd, 3), sstd=round(sstd, 3), mean=round(mm, 3),
                vhist=[round(h * 100 / ht) for h in hist], wave=wave, cells=len(cells))


def pwr_both(a, b, n=200, dt=0.5):
    """Mean leds.pwr of both lamps, read alternately over the same window (n*dt s, default 100 s).
    Two consecutive windows would sit at different phases of a 30-50 s colour cycle (+-25 %)."""
    va, vb = [], []
    for _ in range(n):
        va.append(wledlab.get(a, "/json/info")["leds"]["pwr"]); vb.append(wledlab.get(b, "/json/info")["leds"]["pwr"]); time.sleep(dt)
    return sum(va) / len(va), sum(vb) / len(vb)


def report(ps, fr, ft, pa=None, pb=None):
    a, b = wledlab.metrics(fr), wledlab.metrics(ft); fa, fb = feats(fr), feats(ft)
    ha, hb = wledlab.capture_health(fr, 100), wledlab.capture_health(ft, 100)
    for tag, h in (("ref", ha), ("tgt", hb)):
        if (h["coverage"] or 0) < 0.9 or (h["max_gap"] or 99) > 2.0:
            print(f"  WARNING p{ps} {tag} capture unhealthy: {h}", flush=True)
    cur = "pwr n/a" if pa is None or pb is None else f"pwr {pa:.0f}/{pb:.0f} ratio {pb / pa:.2f}"
    print(f"=== p{ps} {cur} | hz {ha['hz']}/{hb['hz']} gap {ha['max_gap']}/{hb['max_gap']} cells {fa['cells']}/{fb['cells']} | mean {fa['mean']}/{fb['mean']} | swell tstd {fa['tstd']}/{fb['tstd']} sstd {fa['sstd']}/{fb['sstd']} ratio {fa['ratio']}/{fb['ratio']} | act {a['activity']:.3f}/{b['activity']:.3f} fast {a['fast_share']:.3f}/{b['fast_share']:.3f} | huespread {a['hue_spread_mean']:.1f}/{b['hue_spread_mean']:.1f} sat {a['sat_mean']:.2f}/{b['sat_mean']:.2f}", flush=True)
    print(f"  bands ref {fa['bands']} tgt {fb['bands']}\n  vhist ref {fa['vhist']}\n  vhist tgt {fb['vhist']}\n  hue%  ref {a['hue_share']}\n  hue%  tgt {b['hue_share']}\n  hueV  ref {a['hue_v']}\n  hueV  tgt {b['hue_v']}\n  wave ref {fa['wave']}\n  wave tgt {fb['wave']}", flush=True)


def main(argv):
    offline = "--offline" in argv
    presets = [int(x) for x in argv if x != "--offline"] or [1, 3, 4, 5, 2, 14, 12, 13, 7, 9, 10, 11]
    os.makedirs(CAP, exist_ok=True)
    try:
        for ps in presets:
            path = os.path.join(CAP, f"struct-p{ps}.json")
            if offline:
                d = json.load(open(path)); report(ps, d["ref"], d["tgt"]); continue
            fr, ft = wledlab.simultaneous(R, T, 100, preset=ps); time.sleep(3)
            meta = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "preset": ps,
                    "ref": wledlab.lamp_meta(R), "tgt": wledlab.lamp_meta(T)}
            pa, pb = pwr_both(R, T)
            try:
                json.dump({"meta": meta, "ref": fr, "tgt": ft}, open(path, "w"))
            except OSError as e:
                print(f"  capture not saved: {e}", flush=True)
            report(ps, fr, ft, pa, pb)
        print("STRUCT DONE", flush=True)
    finally:
        if not offline:
            for ip in (R, T):
                wledlab.post(ip, "/json/state", {"on": True, "bri": 255, "ps": 4})


if __name__ == "__main__":
    main(sys.argv[1:])
