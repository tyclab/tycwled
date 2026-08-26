#!/usr/bin/env python3
"""wledlab — measure WLED lamps instead of eyeballing them.

Stdlib only. Captures the binary liveview over /ws on both WLED 0.14 and 16
(HTTP /json/live is the fallback for builds without it). All metrics operate on the *logical* frame
(raster cells as the effect engine sees them); physical mapping is checked
separately with `check-ledmap`, because liveview cannot see it.

Subcommands
  capture          record liveview frames from one lamp to a JSON file
  analyse          fingerprint a capture (raster structure, wavelength,
                   drift, hue range/cycle, brightness statistics)
  compare          capture two lamps simultaneously and print metrics side by side
  calibrate-speed  iteratively set the target's `sx` until its stripe drift
                   matches the reference (rate ∝ 10+sx on frame-bound effects)
  check-ledmap     prove the ledmap is applied: white fill current estimate of
                   target vs reference (1.0 = same physical LED count, 1.5 =
                   identity mapping on a 120-cell / 80-LED GLORB)
  push-frame       push one identical frame to both lamps (per-LED JSON API,
                   inverse gamma for 0.14 which gamma-corrects that input)
  install          upload ledmap / presets / palettes byte-exact, reload, verify
  verify           acceptance gate: every preset on both lamps, ABL current
                   estimate ratio target/ref must stay within --tolerance

Recorded knowledge (GLORB, WLED 16.0.1):
  * WLED 16 validates ledmap.json as JSON, then scans the raw bytes for
    `"map":[` to read the array. A space after the colon silently yields an
    identity mapping. `install` refuses such files.
  * uploads take effect without reboot: /palette*.json reload on upload,
    presets are read from the file on every apply, {"ledmap":0} reloads the map.
    Custom palette IDs count down from 200 (palette0 = 200).
  * 16's built-in palettes are re-encoded for its per-pixel gamma; with
    light.gc off, use custom palettes with the 0.14 stop values instead.
  * Colorwaves' hue triangle sweeps palette index 0-127 only; compress a
    palette into 0-127 to get the full gradient.
  * 16 applies gamma to every rendered pixel, 0.14 only to input colours:
    light.gc = {bri:1,col:1,val:1} for the 0.14 look with palette effects.
  * liveview load slows frame-bound effects; use long simultaneous windows.
"""
import argparse
import base64
import colorsys
import json
import math
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

W, H = 20, 6  # GLORB raster; overridable via --width/--height


# ----------------------------------------------------------------------------- http
def get(ip, path, timeout=6):
    return json.load(urllib.request.urlopen(f"http://{ip}{path}", timeout=timeout))


def post(ip, path, obj, timeout=8):
    req = urllib.request.Request(
        f"http://{ip}{path}", data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"}
    )
    return urllib.request.urlopen(req, timeout=timeout).read()


def upload(ip, name, path):
    r = subprocess.run(
        ["curl", "-s", "-m", "30", "-F", f"data=@{path};filename={name}", f"http://{ip}/upload"],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def readback(ip, name):
    return subprocess.run(["curl", "-s", "-m", "10", f"http://{ip}{name}"], capture_output=True).stdout


# ----------------------------------------------------------------------------- liveview
def live_http(ip, seconds):
    """WLED 0.14: /json/live returns logical cells (through the ledmap)."""
    frames, t0 = [], time.time()
    while time.time() - t0 < seconds:
        try:
            frames.append((round(time.time() - t0, 3), get(ip, "/json/live", 4)["leds"]))
        except Exception:
            pass
        time.sleep(0.05)
    return frames


def live_ws(ip, seconds):
    """WLED 0.15+/16: binary liveview over WebSocket ('L', ver, [w, h,] RGB...)."""
    s = socket.create_connection((ip, 80), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(
        f"GET /ws HTTP/1.1\r\nHost: {ip}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode()
    )
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    hdr, buf = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in hdr.split(b"\r\n")[0]:
        raise RuntimeError(hdr[:80])

    def send_text(t):
        p = t.encode(); m = os.urandom(4); n = len(p)
        h = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        s.sendall(h + m + bytes(b ^ m[i % 4] for i, b in enumerate(p)))

    send_text('{"lv":true}')
    frames, t0 = [], time.time()
    s.settimeout(3)
    while time.time() - t0 < seconds:
        while len(buf) >= 2:
            op, ln, o = buf[0] & 0x0F, buf[1] & 0x7F, 2
            if ln == 126:
                if len(buf) < 4:
                    break
                ln, o = struct.unpack(">H", buf[2:4])[0], 4
            elif ln == 127:
                if len(buf) < 10:
                    break
                ln, o = struct.unpack(">Q", buf[2:10])[0], 10
            if len(buf) < o + ln:
                break
            pay, buf = buf[o:o + ln], buf[o + ln:]
            if op == 2 and pay[:1] == b"L":
                ver = pay[1]
                pos = 4 if ver == 2 else 2  # ver 2 carries w,h at [2],[3]
                leds = [pay[pos + 3 * i:pos + 3 * i + 3].hex() for i in range((len(pay) - pos) // 3)]
                frames.append((round(time.time() - t0, 3), leds))
            elif op == 9:
                s.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
        try:
            d = s.recv(4096)
        except socket.timeout:
            d = b""
        if not d:
            break
        buf += d
    send_text('{"lv":false}')
    s.close()
    return frames


def live(ip, seconds):
    """WS liveview on both firmwares (0.14 serves the same 'L' v2 stream); HTTP polling as fallback."""
    try:
        frames = live_ws(ip, seconds)
        if frames:
            return frames
    except (OSError, RuntimeError):
        pass
    return live_http(ip, seconds)


# ----------------------------------------------------------------------------- analysis
def hsv(c):
    return colorsys.rgb_to_hsv(int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255)


def orderings(w, h):
    return {
        "rowmajor": lambda x, y: x + w * y,
        "rowmajor_flipY": lambda x, y: x + w * (h - 1 - y),
        "serpentine": lambda x, y: (x if y % 2 == 0 else w - 1 - x) + w * y,
        "colmajor": lambda x, y: y + h * x,
    }


def r2_1d(bri, idx, lmin=4.0, lmax=40.0):
    m = sum(bri) / len(bri); v = [b - m for b in bri]; tot = sum(a * a for a in v)
    best = (0.0, 0.0)
    for L in [l / 10 for l in range(int(lmin * 10), int(lmax * 10))]:
        re = sum(b * math.cos(2 * math.pi * i / L) for b, i in zip(v, idx))
        im = sum(b * math.sin(2 * math.pi * i / L) for b, i in zip(v, idx))
        a2 = re * re + im * im
        if a2 > best[0]:
            best = (a2, L)
    return (2 * best[0] / len(v) / tot if tot else 0.0), best[1]


def drift_cells_per_s(frames, row, w):
    """Track the brightness peaks of one fully populated row across frames."""
    def peaks(b):
        return [x for x in range(w) if b[x] >= b[(x - 1) % w] and b[x] >= b[(x + 1) % w] and b[x] > sum(b) / w]
    base = row * w
    b = [hsv(c)[2] for c in frames[0][1][base:base + w]]
    p0 = peaks(b); pk: int = p0[0] if p0 else 0; pos = 0
    for _, leds in frames[1:]:
        b = [hsv(c)[2] for c in leds[base:base + w]]; ps = peaks(b)
        if not ps:
            continue
        q = min(ps, key=lambda x: min(abs(x - pk), w - abs(x - pk)))
        d = (q - pk + w // 2) % w - w // 2
        if abs(d) > w // 5:
            continue
        pos += d; pk = q
    dt = frames[-1][0] - frames[0][0]
    return pos / dt if dt else 0.0


def autocorr_peaks(series, dt, maxlag_s):
    m = sum(series) / len(series); v = [a - m for a in series]; den = sum(a * a for a in v) or 1
    ac = [sum(v[i] * v[i + l] for i in range(len(v) - l)) / den for l in range(int(maxlag_s / dt))]
    return [(round(l * dt, 1), round(ac[l], 2)) for l in range(4, len(ac) - 1)
            if ac[l] > ac[l - 1] and ac[l] >= ac[l + 1] and ac[l] > 0.15][:4]


def resample(ts, series, dt=0.5):
    out, t, k = [], 0.0, 0
    while t <= ts[-1]:
        while k + 1 < len(ts) and ts[k + 1] <= t:
            k += 1
        out.append(series[k]); t += dt
    return out


def metrics(frames, w=W, h=H, row=None):
    # cells that light up in any frame (a single frame misses cells at a brightness trough)
    lit = sorted({i for _, leds in frames for i, c in enumerate(leds) if hsv(c)[2] > 0.02})
    X = [i % w for i in lit]; Y = [i // w for i in lit]
    if row is None:  # first fully populated row
        row = next((y for y in range(h) if all(x + w * y in lit for x in range(w))), h // 2)
    m = {"frames": len(frames), "seconds": round(frames[-1][0] - frames[0][0], 1), "lit_cells": len(lit)}
    vals, sats, hmean, spread, contr = [], [], [], [], []
    for _, leds in frames:
        hs = [hsv(leds[i]) for i in lit]
        v = [x[2] * 255 for x in hs]; hh = [x[0] * 360 for x in hs]
        vals += v; sats += [x[1] for x in hs]; hmean.append(sum(hh) / len(hh))
        spread.append(max(hh) - min(hh)); contr.append(max(v) - min(v))
    sv = sorted(vals)
    m.update(bri_mean=sum(vals) / len(vals), bri_p10=sv[len(sv) // 10], bri_p90=sv[len(sv) * 9 // 10],
             contrast_mean=sum(contr) / len(contr), sat_mean=sum(sats) / len(sats),
             hue_spread_mean=sum(spread) / len(spread), hue_min=min(hmean), hue_max=max(hmean))
    step = max(1, len(frames) // 30)
    acc = {k: [] for k in orderings(w, h)}; Ls = []
    for _, leds in frames[::step]:
        bri = [hsv(leds[i])[2] * 255 for i in lit]
        if max(bri) - min(bri) < 30:
            continue
        for k, fn in orderings(w, h).items():
            r, L = r2_1d(bri, [fn(x, y) for x, y in zip(X, Y)]); acc[k].append(r)
            if k == "rowmajor":
                Ls.append(L)
    m["raster_r2"] = {k: round(sum(a) / len(a), 2) if a else None for k, a in acc.items()}
    if Ls:
        m.update(wavelength_min=min(Ls), wavelength_max=max(Ls), stripes_per_turn=round(w / (sum(Ls) / len(Ls)), 2))
    m["drift_cells_per_s"] = drift_cells_per_s(frames, row, w)
    m["turn_seconds"] = (w / abs(m["drift_cells_per_s"])) if m["drift_cells_per_s"] else None
    ts = [f[0] for f in frames]
    if ts[-1] > 20:
        m["hue_cycle_autocorr"] = autocorr_peaks(resample(ts, hmean), 0.5, min(90, ts[-1] / 2))
    return m


def print_metrics(*named):
    keys = ["frames", "seconds", "lit_cells", "bri_mean", "bri_p10", "bri_p90", "contrast_mean", "sat_mean",
            "hue_spread_mean", "hue_min", "hue_max", "wavelength_min", "wavelength_max", "stripes_per_turn",
            "drift_cells_per_s", "turn_seconds"]
    names = [n for n, _ in named]
    print(f"{'metric':<20}" + "".join(f"{n:>16}" for n in names))
    for k in keys:
        row = f"{k:<20}"
        for _, m in named:
            v = m.get(k)
            row += f"{v:>16.2f}" if isinstance(v, float) else f"{str(v):>16}"
        print(row)
    for n, m in named:
        print(f"raster_r2 {n}: {m['raster_r2']}   hue_cycle {m.get('hue_cycle_autocorr')}")


# ----------------------------------------------------------------------------- commands
def cmd_capture(a):
    fr = live(a.host, a.seconds)
    json.dump(fr, open(a.out, "w"))
    print(f"{len(fr)} frames ({len(fr) / a.seconds:.1f} Hz) -> {a.out}")


def cmd_analyse(a):
    fr = json.load(open(a.file))
    fr = [(f[0], f[-1]) for f in fr]
    print_metrics((os.path.basename(a.file), metrics(fr, a.width, a.height)))


def simultaneous(ref, target, seconds, preset=None):
    for ip in (ref, target):
        st = {"on": True, "bri": 255, "seg": [{"id": 0, "frz": False}]}
        if preset:
            st["ps"] = preset
        post(ip, "/json/state", st)
    time.sleep(1.5)
    res = {}
    t1 = threading.Thread(target=lambda: res.__setitem__("ref", live(ref, seconds)))
    t2 = threading.Thread(target=lambda: res.__setitem__("tgt", live(target, seconds)))
    t1.start(); t2.start(); t1.join(); t2.join()
    return res["ref"], res["tgt"]


def cmd_compare(a):
    fr, ft = simultaneous(a.ref, a.target, a.seconds, a.preset)
    print_metrics((f"ref {a.ref}", metrics(fr, a.width, a.height)), (f"target {a.target}", metrics(ft, a.width, a.height)))


def cmd_calibrate_speed(a):
    sx = a.start
    for ip in (a.ref, a.target):
        post(ip, "/json/state", {"on": True, "bri": 255, "ps": a.preset} if a.preset else {"on": True, "bri": 255})
    time.sleep(1.5)
    if a.ref_speed is not None:
        post(a.ref, "/json/state", {"seg": [{"id": a.seg, "sx": a.ref_speed}]})
    for it in range(a.iterations):
        post(a.target, "/json/state", {"seg": [{"id": a.seg, "sx": sx}]}); time.sleep(1.5)
        fr, ft = simultaneous(a.ref, a.target, a.seconds)
        dr = drift_cells_per_s(fr, a.row, a.width); dt = drift_cells_per_s(ft, a.row, a.width)
        ratio = abs(dt / dr) if dr else float("inf")
        print(f"iter {it + 1}: ref {dr:+.2f} cells/s | target sx {sx}: {dt:+.2f} cells/s | ratio {ratio:.2f}")
        if 0.95 < ratio < 1.05:
            break
        sx = max(0, min(255, round((10 + sx) / ratio - 10)))  # frame-bound effects: rate ∝ 10+sx
    print(f"result: target sx = {sx}")
    if a.presets_file and a.preset:
        p = json.load(open(a.presets_file)); p[str(a.preset)]["seg"][0]["sx"] = sx
        json.dump(p, open(a.presets_file, "w"), separators=(",", ":"))
        print(f"written sx={sx} into preset {a.preset} of {a.presets_file} (upload + reboot with `install`)")


def white_estimate(ip, bri):
    # drop every segment but 0 first: a leftover blend layer (composite presets) darkens the fill
    extra = [{"id": x["id"], "stop": 0} for x in get(ip, "/json/state")["seg"] if x["id"] != 0]
    post(ip, "/json/state", {"on": True, "bri": bri, "seg": [{"id": 0, "fx": 0, "pal": 0,
                                                                "col": [[255, 255, 255], [0, 0, 0], [0, 0, 0]], "frz": False}] + extra})
    time.sleep(2.5)
    return sum(get(ip, "/json/info")["leds"]["pwr"] for _ in range(3)) // 3


def cmd_check_ledmap(a):
    pr, pt = white_estimate(a.ref, a.bri), white_estimate(a.target, a.bri)
    ratio = pt / pr if pr else float("inf")
    print(f"white@{a.bri}: ref {pr} mA, target {pt} mA, ratio {ratio:.2f}")
    print("OK: same physical LED count written" if 0.9 < ratio < 1.1 else
          "SUSPECT: target writes a different number of physical LEDs (identity mapping? wrong ledmap?)")
    raw = readback(a.target, "/ledmap.json")
    print("ledmap.json on target contains exact `\"map\":[`:", b'"map":[' in raw)
    for ip in (a.ref, a.target):  # leave the lamps usable: full brightness, boot preset
        post(ip, "/json/state", {"on": True, "bri": 255, "ps": a.restore_preset})


def cmd_verify(a):
    """Output-stage check liveview cannot do: brightness after mapping, gamma, bri and ABL."""
    want = json.load(open(a.presets_file)); fails = []
    for k, v in want.items():
        if not v:
            continue
        for ip in (a.ref, a.target):
            post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(k)})
        time.sleep(2)
        pr, pt = [], []
        for _ in range(a.samples):  # window must cover >= 2 colour cycles (~33 s) — Fire spans black..white
            pr.append(get(a.ref, "/json/info")["leds"]["pwr"]); pt.append(get(a.target, "/json/info")["leds"]["pwr"])
            time.sleep(a.interval)
        r = (sum(pt) / len(pt)) / max(1, sum(pr) / len(pr))
        ok = 1 - a.tolerance <= r <= 1 + a.tolerance
        print(f"  preset {k:>2} {v.get('n', ''):<26} ref {sum(pr) / len(pr):5.0f} mA  target {sum(pt) / len(pt):5.0f} mA  ratio {r:.2f}  {'PASS' if ok else 'FAIL'}")
        fails += [] if ok else [k]
    for ip in (a.ref, a.target):
        post(ip, "/json/state", {"on": True, "bri": 255, "ps": a.restore_preset})
    print("verify:", "PASS" if not fails else f"FAIL {fails}")
    sys.exit(0 if not fails else 1)


GAMMA = [round((x / 255) ** 2.8 * 255) for x in range(256)]


def ginv(v):
    return min(range(256), key=lambda x: (abs(GAMMA[x] - v), x))


def cmd_push_frame(a):
    if a.frame:
        ref = json.load(open(a.frame))
    else:
        post(a.ref, "/json/state", {"seg": [{"id": 0, "frz": True}]}); time.sleep(0.5)
        ref = get(a.ref, "/json/live")["leds"]
        json.dump(ref, open("pushed_frame.json", "w"))
    def arr(inv):
        out = []
        for k, c in enumerate(ref):
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            if inv:
                r, g, b = ginv(r), ginv(g), ginv(b)
            out += [k, f"{r:02x}{g:02x}{b:02x}"]
        return out
    for ip, inv in ((a.target, a.target_input_gamma), (a.ref, a.ref_input_gamma)):
        if ip:
            post(ip, "/json/state", {"on": True, "bri": 255, "seg": [{"id": 0, "i": arr(inv)}]})
    print(f"frame ({len(ref)} cells) pushed; lamps are frozen — unfreeze with a preset or {{\"seg\":[{{\"frz\":false}}]}}")


def cmd_install(a):
    if a.ledmap:
        raw = open(a.ledmap, "rb").read()
        if b'"map":[' not in raw:
            sys.exit("REFUSED: ledmap must contain the exact bytes \"map\":[ (WLED 16 scans the raw file for them)")
        print("ledmap:", upload(a.host, "/ledmap.json", a.ledmap), "| readback ok:", readback(a.host, "/ledmap.json") == raw)
        if not a.reboot:
            post(a.host, "/json/state", {"ledmap": 0})
    for n, f in enumerate(a.palette or []):
        print(f"palette{n}:", upload(a.host, f"/palette{n}.json", f), "| readback ok:", readback(a.host, f"/palette{n}.json") == open(f, "rb").read())
    if a.presets:
        print("presets:", upload(a.host, "/presets.json", a.presets), "| readback ok:",
              json.loads(readback(a.host, "/presets.json")) == json.load(open(a.presets)))
    if a.reboot:
        post(a.host, "/json/state", {"rb": True})
        for _ in range(30):
            time.sleep(4)
            try:
                get(a.host, "/json/info"); break
            except Exception:
                pass
    info = get(a.host, "/json/info")
    print("rebooted:" if a.reboot else "live:", info["ver"], "matrix", info["leds"].get("matrix"),
          "ledmap", get(a.host, "/json/state").get("ledmap"), "custom palettes", info.get("cpalcount"))
    if a.palette and info.get("cpalcount", 0) < len(a.palette):
        sys.exit(f"custom palettes: lamp reports {info.get('cpalcount')}, uploaded {len(a.palette)}")
    if a.presets:
        want = json.load(open(a.presets)); bad = []
        keys = ("fx", "sx", "ix", "pal", "c1", "c2", "c3", "o1", "o2", "o3", "m12", "tp", "rY", "rev", "mi", "mY",
                "bm", "bri", "col", "start", "stop", "startY", "stopY")
        for k, v in want.items():
            if not v:
                continue
            post(a.host, "/json/state", {"on": True, "ps": int(k)}); time.sleep(0.5)
            segs = get(a.host, "/json/state")["seg"]
            ok = True
            for ws in v["seg"]:
                s = next((x for x in segs if x["id"] == ws["id"]), {})
                if ws.get("stop") == 0:
                    ok &= s.get("stop", 0) == 0
                else:
                    ok &= all(s.get(x) == ws.get(x) for x in keys if x in ws)
                    if 180 < ws.get("pal", 0) <= 200 and ws["pal"] < 201 - info.get("cpalcount", 0):
                        ok = False  # custom palette id with no uploaded file behind it
            print(f"  preset {k:>2} {v.get('n', ''):<26} {'OK' if ok else 'MISMATCH'}")
            bad += [] if ok else [k]
        print("preset verification:", "all OK" if not bad else f"MISMATCH {bad}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--width", type=int, default=W); p.add_argument("--height", type=int, default=H)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("capture"); s.add_argument("--host", required=True); s.add_argument("--seconds", type=float, default=60); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_capture)
    s = sub.add_parser("analyse"); s.add_argument("file"); s.set_defaults(fn=cmd_analyse)
    s = sub.add_parser("compare"); s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--seconds", type=float, default=120); s.add_argument("--preset", type=int); s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("calibrate-speed"); s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--seconds", type=float, default=120)
    s.add_argument("--preset", type=int); s.add_argument("--ref-speed", type=int); s.add_argument("--start", type=int, default=4); s.add_argument("--iterations", type=int, default=3)
    s.add_argument("--seg", type=int, default=0); s.add_argument("--row", type=int, default=2); s.add_argument("--presets-file"); s.set_defaults(fn=cmd_calibrate_speed)
    s = sub.add_parser("check-ledmap"); s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--bri", type=int, default=64); s.add_argument("--restore-preset", type=int, default=1); s.set_defaults(fn=cmd_check_ledmap)
    s = sub.add_parser("push-frame"); s.add_argument("--ref"); s.add_argument("--target"); s.add_argument("--frame")
    s.add_argument("--ref-input-gamma", action="store_true", help="ref is 0.14 (gamma-corrects per-LED input)"); s.add_argument("--target-input-gamma", action="store_true"); s.set_defaults(fn=cmd_push_frame)
    s = sub.add_parser("verify"); s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--presets-file", required=True); s.add_argument("--samples", type=int, default=140); s.add_argument("--interval", type=float, default=0.5); s.add_argument("--tolerance", type=float, default=0.15); s.add_argument("--restore-preset", type=int, default=1); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("install"); s.add_argument("--host", required=True); s.add_argument("--ledmap"); s.add_argument("--presets"); s.add_argument("--palette", action="append"); s.add_argument("--reboot", action="store_true"); s.set_defaults(fn=cmd_install)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
