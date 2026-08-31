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

Metrics printed by analyse/compare: bri_* from all lit cells (0-255, liveview
is pre-brightness), sat/hue from cells above 20 % brightness (black has no
hue), hue_spread = mean angular deviation across the raster per frame,
raster_r2 = variance explained by the best sinusoid per cell ordering (1.0 =
pure wave; may exceed 1 on sparse rows), wavelength = that sinusoid's period
in cells (snaps to whole stripes per ring on short rows — trust
stripe_period, the autocorrelation peak along the full middle rows, when
they disagree), drift in cells/s (sign = direction), hue_cycle_autocorr =
(lag s, correlation) peaks of the mean hue as a unit vector, i.e. candidate
colour-cycle periods, activity = mean brightness change per lit cell per
second (speed of any effect, including plasma and sparkle; compare ratios),
activity_rel = the same divided by mean brightness (activity scales with bri).

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
def _retry(fn, attempts=4):
    # an ESP32 drops the odd request; one timeout must not kill a 15-minute gate run
    for i in range(attempts):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == attempts - 1:
                raise
            time.sleep(2)


def get(ip, path, timeout=6):
    return _retry(lambda: json.load(urllib.request.urlopen(f"http://{ip}{path}", timeout=timeout)))


def post(ip, path, obj, timeout=8):
    req = urllib.request.Request(
        f"http://{ip}{path}", data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"}
    )
    return _retry(lambda: urllib.request.urlopen(req, timeout=timeout).read())


def upload(ip, name, path):
    r = subprocess.run(
        ["curl", "-s", "-m", "30", "-F", f"data=@{path};filename={name}", f"http://{ip}/upload"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"upload {path} -> {ip}{name}: curl exit {r.returncode} {r.stderr.strip()}")
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
    except (OSError, RuntimeError) as e:
        print(f"WARN {ip}: WS liveview failed ({e}); HTTP polling fallback -- different instrument, lower rate", flush=True)
        return live_http(ip, seconds)
    print(f"WARN {ip}: WS liveview yielded no frames; HTTP polling fallback", flush=True)
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


def stripe_period(frames, w, h):
    """Median first autocorrelation peak of brightness along the full middle rows (cells)."""
    rows = [y for y in range(h) if h // 2 - 1 <= y <= h // 2]
    seq_idx = [x + w * y for y in rows for x in range(w)]
    ps = []
    for _, leds in frames[::max(1, len(frames) // 20)]:
        s = [hsv(leds[i])[2] for i in seq_idx]
        m = sum(s) / len(s); d = [x - m for x in s]; den = sum(x * x for x in d) or 1
        ac = [sum(d[i] * d[i + l] for i in range(len(d) - l)) / den for l in range(0, len(d) // 2)]
        pk = [l for l in range(3, len(ac) - 1) if ac[l] > ac[l - 1] and ac[l] >= ac[l + 1] and ac[l] > 0.1]
        if pk:
            ps.append(pk[0])
    ps.sort()
    return ps[len(ps) // 2] if ps else None


def activity(frames, dt=1.0):
    """Mean |Δbrightness| per lit cell over dt seconds (0..1): how fast the pattern moves, any effect."""
    vals, j = [], 0
    for t, leds in frames:
        while j < len(frames) and frames[j][0] < t + dt:
            j += 1
        if j >= len(frames):
            break
        a = [hsv(c)[2] for c in leds]; b = [hsv(c)[2] for c in frames[j][1]]
        lit = [k for k in range(len(a)) if a[k] > 0.02 or b[k] > 0.02]
        if lit:
            vals.append(sum(abs(a[k] - b[k]) for k in lit) / len(lit))
    return sum(vals) / len(vals) if vals else 0.0


def hue_cycle_peaks(ts, hues_deg, dt=0.5, maxlag_s=90):
    """Autocorrelation of the mean hue as a unit vector (no wrap artefacts); (lag s, correlation) peaks."""
    n = int(ts[-1] / dt); cs, ss, j = [], [], 0
    for k in range(n):
        while j + 1 < len(ts) and ts[j + 1] <= k * dt:
            j += 1
        a = hues_deg[j] * math.pi / 180; cs.append(math.cos(a)); ss.append(math.sin(a))
    mc, ms = sum(cs) / n, sum(ss) / n; dc = [c - mc for c in cs]; ds = [x - ms for x in ss]
    den = sum(a * a + b * b for a, b in zip(dc, ds)) or 1
    L = min(int(maxlag_s / dt), n // 2)
    ac = [sum(dc[i] * dc[i + l] + ds[i] * ds[i + l] for i in range(n - l)) / den for l in range(L)]
    return [(round(l * dt, 1), round(ac[l], 2)) for l in range(4, len(ac) - 1)
            if ac[l] > ac[l - 1] and ac[l] >= ac[l + 1] and ac[l] > 0.15][:4]


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


def hue_census(frames, bins=12):
    """Share of lit cell-samples per 30-degree hue bin (%), and their mean brightness (0..255).
    Catches a palette used over the wrong range or dwelling in the wrong colours (Black Hole - Sunset:
    fork 100 % red/orange, a whole-palette port 36 %)."""
    n = [0] * bins; v = [0] * bins
    for _, leds in frames[::3]:
        for c in leds:
            h, s_, val = hsv(c)
            if val > 0.05:
                k = int(h * bins) % bins; n[k] += 1; v[k] += val * 255
    tot = sum(n) or 1
    return [round(x * 100 / tot) for x in n], [round(v[k] / n[k]) if n[k] else None for k in range(bins)]


def fast_share(frames, fs=10, split_hz=1.0):
    """Share of per-cell brightness variance faster than split_hz (0..1): sub-second shimmer that activity()
    averages away (fork Hiphotic ~0.01, 16 Hiphotic at c3 12 ~0.06 — visibly 'too fast')."""
    t0 = frames[0][0]; n = int((frames[-1][0] - t0) * fs)
    if n < 4 * fs:
        return None
    cells = sorted({i for _, leds in frames for i, c in enumerate(leds) if hsv(c)[2] > 0.05})
    series = {c: [] for c in cells}; j = 0
    for k in range(n):
        t = t0 + k / fs
        while j + 1 < len(frames) and frames[j + 1][0] <= t:
            j += 1
        for c in cells:
            series[c].append(hsv(frames[j][1][c])[2])
    cs = [[math.cos(2 * math.pi * k * i / n) for i in range(n)] for k in range(1, n // 2)]
    sn = [[math.sin(2 * math.pi * k * i / n) for i in range(n)] for k in range(1, n // 2)]
    slow = fast = 0.0
    for s in series.values():
        m = sum(s) / n; d = [x - m for x in s]
        for k in range(1, n // 2):
            re = sum(a * b for a, b in zip(d, cs[k - 1])); im = sum(a * b for a, b in zip(d, sn[k - 1]))
            if k * fs / n < split_hz:
                slow += re * re + im * im
            else:
                fast += re * re + im * im
    return fast / (slow + fast) if slow + fast else None


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
        v = [x[2] * 255 for x in hs]
        vals += v; contr.append(max(v) - min(v))
        bright = [x for x in hs if x[2] > 0.2] or hs  # black cells have no hue
        sats += [x[1] for x in bright]
        cx = sum(math.cos(x[0] * 2 * math.pi) for x in bright); cy = sum(math.sin(x[0] * 2 * math.pi) for x in bright)
        mh = math.atan2(cy, cx); hmean.append((mh / (2 * math.pi)) % 1 * 360)
        spread.append(sum(abs(math.atan2(math.sin(x[0] * 2 * math.pi - mh), math.cos(x[0] * 2 * math.pi - mh))) for x in bright) / len(bright) * 180 / math.pi)
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
    m["stripe_period"] = stripe_period(frames, w, h)  # robust where the sinusoid fit snaps to whole stripes per ring
    m["activity"] = activity(frames)  # speed measure that also works for plasma/sparkle effects
    m["activity_rel"] = m["activity"] / max(1e-6, m["bri_mean"] / 255)  # brightness-normalised: compare lamps at different bri
    m["fast_share"] = fast_share(frames)
    m["hue_share"], m["hue_v"] = hue_census(frames)
    m["drift_cells_per_s"] = drift_cells_per_s(frames, row, w)
    m["turn_seconds"] = (w / abs(m["drift_cells_per_s"])) if m["drift_cells_per_s"] else None
    ts = [f[0] for f in frames]
    if ts[-1] > 20:
        m["hue_cycle_autocorr"] = hue_cycle_peaks(ts, hmean, 0.5, min(90, ts[-1] / 2))
    return m


def print_metrics(*named):
    keys = ["frames", "seconds", "lit_cells", "bri_mean", "bri_p10", "bri_p90", "contrast_mean", "sat_mean",
            "hue_spread_mean", "hue_min", "hue_max", "wavelength_min", "wavelength_max", "stripe_period", "stripes_per_turn",
            "drift_cells_per_s", "turn_seconds", "activity", "activity_rel", "fast_share"]
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
    for n, m in named:
        print(f"hue_share {n}: {m['hue_share']}  hue_v {m['hue_v']}")


# ----------------------------------------------------------------------------- structural gate
def structural_stats(frames, step=3):
    """Per-cell V statistics for the acceptance gate: V-histogram (10 bins, share of lit-cell
    samples), temporal std of the frame mean, mean spatial std, median frame peak, mean lit count.
    Lit = cells that ever exceed 0.05 (excludes ledmap holes without needing the map)."""
    vs = [[hsv(c)[2] for c in f[1]] for f in frames[::step]]
    n = len(vs[0]); lit = [i for i in range(n) if max(v[i] for v in vs) > 0.05]
    if not lit:  # all-dark capture: a mis-installed preset must FAIL, not crash the run
        return dict(vhist=[0.0] * 10, mean=0.0, tstd=0.0, sstd=0.0, peak=0.0, lit=0.0)
    hist = [0] * 10; means = []; sstds = []; peaks = []; litn = []
    for v in vs:
        vals = [v[i] for i in lit]
        m = sum(vals) / len(vals); means.append(m)
        sstds.append((sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5)
        peaks.append(max(vals)); litn.append(sum(1 for x in vals if x > 0.05))
        for x in vals:
            hist[min(9, int(x * 10))] += 1
    ht = sum(hist) or 1; mm = sum(means) / len(means)
    tstd = (sum((x - mm) ** 2 for x in means) / len(means)) ** 0.5
    return dict(vhist=[h / ht for h in hist], mean=mm, tstd=tstd, sstd=sum(sstds) / len(sstds),
                peak=sorted(peaks)[len(peaks) // 2], lit=sum(litn) / len(litn))


def hue_shares(frames, bins=12, step=3):
    """Unrounded hue census shares (fractions summing to 1) for the gate's EMD.
    Same semantics as hue_census (lit = V > 0.05) but without integer-percent rounding."""
    cnt = [0.0] * bins; tot = 0
    for _, leds in frames[::step]:
        for c in leds:
            h, s, v = hsv(c)
            if v > 0.05:
                cnt[int(h * bins) % bins] += 1; tot += 1
    return [x / tot for x in cnt] if tot else cnt


def circ_emd(p, q):
    """Earth-mover distance between two circular 12-bin distributions (shares summing to 1):
    L1 of the median-shifted prefix sums. Robust to a sub-bin hue shift splitting one colour
    across the 0/11 bin edge, which plain per-bin L1 is not."""
    assert len(p) == len(q), "circ_emd: length mismatch"
    d = [x - y for x, y in zip(p, q)]
    pre = []; acc = 0.0
    for x in d:
        acc += x; pre.append(acc)
    med = sorted(pre)[len(pre) // 2]
    return sum(abs(x - med) for x in pre)


def gate_scores(fr, ft):
    """Structural comparison for the gate: distances/ratios of target vs ref."""
    a, b = structural_stats(fr), structural_stats(ft)
    vd = sum(abs(x - y) for x, y in zip(a["vhist"], b["vhist"])) / 2
    hd = circ_emd(hue_shares(fr), hue_shares(ft))

    def rat(x, y):
        return (y / x) if x else None

    return dict(vhist_d=vd, hue_d=hd, sstd_r=rat(a["sstd"], b["sstd"]), act_r=rat(activity(fr), activity(ft)),
                peak_r=rat(a["peak"], b["peak"]), lit_r=rat(a["lit"], b["lit"]), mean_r=rat(a["mean"], b["mean"]))


def capture_health(frames, seconds=None):
    """Instrument self-check: achieved rate, window coverage and frame-interval gaps.
    A capture with low coverage or a multi-second gap measured a different window than
    its partner and must not be scored silently."""
    ts = [t for t, _ in frames]
    if len(ts) < 2:
        return dict(frames=len(ts), hz=0.0, coverage=0.0, max_gap=None, p95_gap=None)
    span = ts[-1] - ts[0]
    gaps = sorted(b - a for a, b in zip(ts, ts[1:]))
    return dict(frames=len(ts), hz=round((len(ts) - 1) / span, 1) if span else 0.0,
                coverage=round(span / seconds, 3) if seconds else None,
                max_gap=round(gaps[-1], 3), p95_gap=round(gaps[int(len(gaps) * 0.95)], 3))


def lamp_meta(ip):
    """Provenance stamp for a capture: firmware, fps, ABL config and the full segment state."""
    info = get(ip, "/json/info"); st = get(ip, "/json/state")
    leds = info.get("leds", {})
    return {"ip": ip, "ver": info.get("ver"), "fps": leds.get("fps"), "maxpwr": leds.get("maxpwr"),
            "cpalcount": info.get("cpalcount"), "wifi": info.get("wifi"), "state": st}



# ----------------------------------------------------------------------------- commands
def cmd_capture(a):
    meta = lamp_meta(a.host)
    fr = live(a.host, a.seconds)
    if not fr:
        sys.exit(f"no frames from {a.host} — lamp busy or liveview refused; retry")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"meta": meta, "frames": fr}, open(a.out, "w"))
    print(f"{len(fr)} frames ({len(fr) / a.seconds:.1f} Hz) -> {a.out}")


def load_capture(path):
    """All capture formats: bare frame list, {'meta','frames'}, {'ref','tgt'[,'meta']}; .gz transparently."""
    import gzip
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt") as f:
        d = json.load(f)
    if isinstance(d, list):
        return {"": d}
    if "frames" in d:
        return {"": d["frames"]}
    out = {k: d[k] for k in ("ref", "tgt") if k in d}
    if not out:
        raise ValueError(f"{path}: unrecognised capture format")
    return out


def cmd_analyse(a):
    named = []
    for f in a.file:
        for tag, fr in load_capture(f).items():
            fr = [(x[0], x[-1]) for x in fr]
            named.append((os.path.basename(f) + (f":{tag}" if tag else ""), metrics(fr, a.width, a.height)))
    print_metrics(*named)


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
    """Acceptance gate. Per preset: one shared window in which both lamps are captured over
    liveview (structural criteria) while their ABL current estimates are sampled alternately
    (the output-stage criterion liveview cannot see). Current is measured UNDER liveview load
    (both lamps stream), and is a first moment -- never the only criterion (--current-only =
    legacy). A crash on one preset records a FAIL and continues; lamps are always restored."""
    import hashlib
    raw = open(a.presets_file, "rb").read(); want = json.loads(raw); fails = []
    n = sum(1 for v in want.values() if v)
    window = a.samples * a.interval
    fmt = lambda x: "n/a" if x is None else f"{x:.2f}"
    print(f"verify: presets.json sha256 {hashlib.sha256(raw).hexdigest()}")
    for tag, ip in (("ref", a.ref), ("target", a.target)):
        m = lamp_meta(ip)
        print(f"  {tag} {ip}: ver {m['ver']} fps {m['fps']} maxpwr {m['maxpwr']} cpalcount {m['cpalcount']} rssi {(m['wifi'] or {}).get('rssi')}")
    print(f"verify: {n} presets, {window:.0f} s each (~{n * (window + 20) / 60:.0f} min); both lamps end on preset {a.restore_preset}", flush=True)
    try:
        for k, v in want.items():
            if not v:
                continue
            try:
                for ip in (a.ref, a.target):
                    post(ip, "/json/state", {"on": True, "bri": 255, "ps": int(k)})
                time.sleep(2)
                bad = [ip for ip in (a.ref, a.target) if get(ip, "/json/state").get("ps") != int(k)]
                if bad:
                    print(f"  preset {k:>2} {v.get('n', ''):<26} FAIL (preset did not apply on {bad})", flush=True)
                    fails.append(k); continue
                meta = {"preset": int(k), "ref": lamp_meta(a.ref), "tgt": lamp_meta(a.target)} if a.save_captures else None
                res = {}
                t1 = threading.Thread(target=lambda: res.__setitem__("ref", live(a.ref, window)))
                t2 = threading.Thread(target=lambda: res.__setitem__("tgt", live(a.target, window)))
                if not a.current_only:
                    t1.start(); t2.start()
                pr, pt = [], []
                t0 = time.time()
                while time.time() - t0 < window:  # wall clock: GET latency must not stretch past the capture
                    pr.append(get(a.ref, "/json/info")["leds"]["pwr"]); pt.append(get(a.target, "/json/info")["leds"]["pwr"])
                    time.sleep(a.interval)
                mr, mt = sum(pr) / len(pr), sum(pt) / len(pt)
                checks = []; line = f"ref {mr:5.0f} mA  target {mt:5.0f} mA"
                if mr < 50 or mt < 50:  # ABL off reports ~0 -- a ratio against the floor guard is noise, not a verdict
                    line += "  current n/a (ABL off or dark)"
                else:
                    r = mt / mr
                    checks.append(("current", 1 - a.tolerance <= r <= 1 + a.tolerance)); line += f"  ratio {r:.3f}"
                if not a.current_only:
                    t1.join(); t2.join()
                    fr, ft = res.get("ref") or [], res.get("tgt") or []
                    if a.save_captures and fr and ft:
                        os.makedirs(a.save_captures, exist_ok=True)
                        json.dump({"meta": meta, "ref": fr, "tgt": ft}, open(os.path.join(a.save_captures, f"verify-p{k}.json"), "w"))
                    hr, ht = capture_health(fr, window), capture_health(ft, window)
                    unhealthy = [t for t, h in (("ref", hr), ("tgt", ht))
                                 if h["frames"] < 10 or h["coverage"] is None or h["coverage"] < 0.9
                                 or h["max_gap"] is None or h["max_gap"] > 2.0]
                    line += f"  hz {hr['hz']}/{ht['hz']} cov {hr['coverage']}/{ht['coverage']} gap {hr['max_gap']}/{ht['max_gap']}"
                    if unhealthy:
                        checks.append(("capture", False)); line += f"  capture UNHEALTHY ({','.join(unhealthy)})"
                    else:
                        g = gate_scores(fr, ft)
                        rng = lambda x, tol: x is not None and 1 / tol <= x <= tol
                        checks += [("vhist", g["vhist_d"] <= a.vhist_tol),
                                   ("hue", g["hue_d"] <= a.hue_tol),
                                   ("sstd", rng(g["sstd_r"], a.sstd_tol)),
                                   ("act", rng(g["act_r"], a.act_tol)),
                                   ("peak", rng(g["peak_r"], a.peak_tol)),
                                   ("lit", rng(g["lit_r"], a.lit_tol))]
                        line += (f"  vhist {g['vhist_d']:.2f} hue {g['hue_d']:.2f} sstd_r {fmt(g['sstd_r'])}"
                                 f" act_r {fmt(g['act_r'])} peak_r {fmt(g['peak_r'])} lit_r {fmt(g['lit_r'])}")
                bad = [c for c, ok in checks if not ok]
                print(f"  preset {k:>2} {v.get('n', ''):<26} {line}  {'PASS' if not bad else 'FAIL ' + ','.join(bad)}", flush=True)
                fails += [] if not bad else [k]
            except Exception as e:  # a broken preset must not cost the remaining ~20 min of run
                print(f"  preset {k:>2} {v.get('n', ''):<26} FAIL (error: {e})", flush=True)
                fails.append(k)
    finally:
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
    p.add_argument("--width", type=int, default=W, help="raster width the lamp reports (GLORB 20)")
    p.add_argument("--height", type=int, default=H, help="raster height (GLORB 6)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("capture", help="record liveview frames from one lamp")
    s.add_argument("--host", required=True, help="lamp IP or hostname"); s.add_argument("--seconds", type=float, default=120, help="capture length (default 120)")
    s.add_argument("--out", required=True, help="output JSON (directory is created)"); s.set_defaults(fn=cmd_capture)
    s = sub.add_parser("analyse", help="fingerprint one or more captures side by side"); s.add_argument("file", nargs="+"); s.set_defaults(fn=cmd_analyse)
    s = sub.add_parser("compare", help="capture two lamps at the same time and print metrics side by side")
    s.add_argument("--ref", required=True, help="reference lamp (factory firmware)"); s.add_argument("--target", required=True, help="lamp under test")
    s.add_argument("--seconds", type=float, default=120, help="window per capture (default 120)"); s.add_argument("--preset", type=int, help="recall this preset on both lamps first"); s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("calibrate-speed", help="iterate the target's sx until its drift matches the reference")
    s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--seconds", type=float, default=120, help="window per iteration")
    s.add_argument("--preset", type=int, help="preset to calibrate (recalled on both)"); s.add_argument("--ref-speed", type=int, help="set this sx on the reference first")
    s.add_argument("--start", type=int, default=4, help="first sx to try on the target"); s.add_argument("--iterations", type=int, default=3)
    s.add_argument("--seg", type=int, default=0, help="segment carrying the effect"); s.add_argument("--row", type=int, default=2, help="raster row to track")
    s.add_argument("--presets-file", help="write the final sx into this presets.json"); s.set_defaults(fn=cmd_calibrate_speed)
    s = sub.add_parser("check-ledmap", help="white fill on both lamps, compare ABL current estimates (1.0 = same LED count)")
    s.add_argument("--ref", required=True); s.add_argument("--target", required=True); s.add_argument("--bri", type=int, default=64, help="fill brightness (default 64)")
    s.add_argument("--restore-preset", type=int, default=1, help="preset both lamps end on"); s.set_defaults(fn=cmd_check_ledmap)
    s = sub.add_parser("push-frame", help="push one identical frame to both lamps via the per-LED JSON API")
    s.add_argument("--ref"); s.add_argument("--target"); s.add_argument("--frame", help="JSON list of hex colours, default: uniform grey 40")
    s.add_argument("--ref-input-gamma", action="store_true", help="ref is 0.14 (gamma-corrects per-LED input)"); s.add_argument("--target-input-gamma", action="store_true"); s.set_defaults(fn=cmd_push_frame)
    s = sub.add_parser("verify", help="acceptance gate: current ratio plus structural criteria (V-hist, hue EMD, spatial std, activity, peak, lit) from a same-window liveview capture")
    s.add_argument("--ref", required=True, help="factory lamp"); s.add_argument("--target", required=True, help="ported lamp"); s.add_argument("--presets-file", required=True)
    s.add_argument("--samples", type=int, default=200, help="current samples per preset (default 140)"); s.add_argument("--interval", type=float, default=0.5, help="seconds between samples (default 0.5 → 70 s window)")
    s.add_argument("--tolerance", type=float, default=0.15, help="allowed deviation of target/ref current (default 0.15)")
    s.add_argument("--current-only", action="store_true", help="legacy gate: current ratio only, no structural criteria")
    s.add_argument("--vhist-tol", type=float, default=0.25, help="max V-histogram L1/2 distance (accepted presets measure <= 0.18; p14 fails at 0.37)")
    s.add_argument("--hue-tol", type=float, default=0.70, help="max circular EMD between hue censuses (run-to-run spread on accepted presets reaches 0.56 -- window phase vs the 30-50 s colour cycle; real mismatch p10 measures >= 1.08)")
    s.add_argument("--sstd-tol", type=float, default=1.6, help="max spatial-std ratio either way (accepted <= 1.13; p14 fails at 0.43)")
    s.add_argument("--act-tol", type=float, default=1.4, help="max activity ratio either way (accepted presets measure <= 1.12; p10 fails at 1.46)")
    s.add_argument("--peak-tol", type=float, default=1.5, help="max median-frame-peak ratio either way (sparkle/swell brightness; p11 port peaks at 0.53)")
    s.add_argument("--lit-tol", type=float, default=1.6, help="max mean lit-cell-count ratio either way (p7 stock 8-frizzle floor reads 1.46 -- recorded limitation, passes)")
    s.add_argument("--save-captures", default="", metavar="DIR", help="save each preset capture as DIR/verify-pN.json with per-preset lamp meta")
    s.add_argument("--restore-preset", type=int, default=1, help="preset both lamps end on"); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("install", help="upload files byte-exact, reload, verify every preset")
    s.add_argument("--host", required=True); s.add_argument("--ledmap"); s.add_argument("--presets"); s.add_argument("--palette", action="append", help="palette file; paletteN.json in order, repeatable")
    s.add_argument("--reboot", action="store_true", help="reboot after upload instead of live reload"); s.set_defaults(fn=cmd_install)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
