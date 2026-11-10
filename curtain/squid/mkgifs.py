#!/usr/bin/env python3
"""Render the squid loops in headless Chromium and write them as GIFs.

draw.js holds the drawing: the curtain's five loops at the ledmap's 68x42 cells, and the arm
waves for the other lamps at their own sizes (fleet/squid/). Each loop is reduced to one
256-colour table and written as whole frames, the form WLED's Image effect plays from the
controller's filesystem. Standard library only; Chromium does the drawing.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CURTAIN = os.path.dirname(HERE)
ROWS = os.path.join(os.path.dirname(CURTAIN), "fleet", "squid")
NAMES = {"a": "squid-breathing", "b": "squid-ink", "c": "squid-deepsea", "e": "squid-eyes", "f": "squid-skin"}
# A pixel whose channels all stay below this is stored as black: the controller's gamma leaves it dark anyway.
BLACK_BELOW = 24
# Lowest level the controller still lights with gamma 2.8 at the presets' brightness 160; used for the printed share only.
ON_LEVEL = 41
# WLED's own table for an output gamma of 2.8 (colour gamma on, as the curtain, the couch and the Moon run).
GAMMA_28 = [int((i / 255) ** 2.8 * 255 + 0.5) for i in range(256)]

RENDER = """
const SS = 4, res = {};
for (const [id, lp] of Object.entries({ ...LOOPS, ...ROWS })) {
  const w = lp.w || W, h = lp.h || H, hi = document.createElement('canvas'), lo = document.createElement('canvas');
  hi.width = w * SS; hi.height = h * SS; lo.width = w; lo.height = h;
  const g = hi.getContext('2d'), l = lo.getContext('2d', { willReadFrequently: true });
  const n = Math.round(lp.L / lp.delay), buf = new Uint8Array(n * w * h * 3); let o = 0;
  for (let f = 0; f < n; f++) {
    g.setTransform(SS, 0, 0, SS, 0, 0); g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1;
    g.fillStyle = '#000'; g.fillRect(0, 0, w, h); g.save(); lp.draw(g, f * lp.delay); g.restore();
    l.imageSmoothingEnabled = true; l.imageSmoothingQuality = 'high'; l.drawImage(hi, 0, 0, w, h);
    const d = l.getImageData(0, 0, w, h).data;
    for (let i = 0; i < d.length; i += 4) { buf[o++] = d[i]; buf[o++] = d[i + 1]; buf[o++] = d[i + 2]; }
  }
  let s = ''; for (let i = 0; i < buf.length; i += 32768) s += String.fromCharCode.apply(null, buf.subarray(i, i + 32768));
  res[id] = { n, delay: lp.delay, L: lp.L, w, h, lampGamma: lp.lampGamma || 2.8, rgb: btoa(s) };
}
document.getElementById('out').textContent = JSON.stringify(res);
"""


def render(chrome, workdir):
    page = os.path.join(workdir, "squid-render.html")
    with open(page, "w") as f:
        f.write("<!doctype html><meta charset=utf-8><pre id=out></pre><script>"
                + open(os.path.join(HERE, "draw.js")).read() + RENDER + "</script>")
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=60000",
                        "--dump-dom", "file://" + page], capture_output=True, env=env, timeout=300)
    os.remove(page)
    m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
    if not m:
        sys.exit("Chromium returned no frames\n" + r.stderr.decode()[-600:])
    return json.loads(m.group(1))


def median_cut(items, n):
    """items: [(r, g, b, count)] -> (palette, {colour: index}) with at most n entries."""
    def stats(box):
        rng = [max(c[ch] for c in box) - min(c[ch] for c in box) for ch in range(3)]
        ch = rng.index(max(rng))
        return (rng[ch], ch, box)

    boxes = [stats(items)]
    while len(boxes) < n:
        boxes.sort(key=lambda b: (b[0], len(b[2])))
        rng, ch, box = boxes[-1]
        if rng == 0:
            break
        boxes.pop()
        box.sort(key=lambda c: c[ch])
        half, acc = sum(c[3] for c in box) / 2, 0
        for i, c in enumerate(box[:-1]):
            acc += c[3]
            if acc >= half and box[i + 1][ch] != c[ch]:
                cut = i + 1
                break
        else:
            cut = next(i + 1 for i in range(len(box) - 1) if box[i + 1][ch] != box[i][ch])
        boxes += [stats(box[:cut]), stats(box[cut:])]
    pal, index = [], {}
    for _, _, box in boxes:
        tot = sum(c[3] for c in box)
        pal.append(tuple(round(sum(c[ch] * c[3] for c in box) / tot) for ch in range(3)))
        for c in box:
            index[c[:3]] = len(pal) - 1
    return pal, index


def lzw(indices, mcs):
    clear, eoi = 1 << mcs, (1 << mcs) + 1
    out, cur, nbits = bytearray(), 0, 0
    table, nxt, size = {}, eoi + 1, mcs + 1

    def emit(code):
        nonlocal cur, nbits
        cur |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(cur & 255)
            cur >>= 8
            nbits -= 8

    emit(clear)
    prefix = indices[0]
    for k in indices[1:]:
        key = (prefix << 8) | k
        if key in table:
            prefix = table[key]
            continue
        emit(prefix)
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            # The reader grows its code width one entry later than the writer adds one.
            if nxt > (1 << size) and size < 12:
                size += 1
        else:
            emit(clear)
            table, nxt, size = {}, eoi + 1, mcs + 1
        prefix = k
    emit(prefix)
    emit(eoi)
    if nbits:
        out.append(cur & 255)
    return bytes(out)


def gif(pal, frames, delay_cs, w, h):
    bits = max(1, (len(pal) - 1).bit_length())
    table = b"".join(bytes(c) for c in pal) + bytes(3 * ((1 << bits) - len(pal)))

    def le(v):
        return v.to_bytes(2, "little")

    out = bytearray(b"GIF89a" + le(w) + le(h) + bytes([0xF0 | (bits - 1), 0, 0]) + table)
    out += b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00"
    mcs = max(2, bits)
    for f in frames:
        out += b"\x21\xF9\x04\x04" + le(delay_cs) + b"\x00\x00"
        out += b"\x2C" + le(0) + le(0) + le(w) + le(h) + b"\x00" + bytes([mcs])
        data = lzw(f, mcs)
        for i in range(0, len(data), 255):
            out += bytes([len(data[i:i + 255])]) + data[i:i + 255]
        out += b"\x00"
    return bytes(out + b"\x3B")


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--chrome", required=True, help="a Chromium binary; it renders the frames headless")
    ap.add_argument("--magick", help="an ImageMagick binary; decodes every written GIF and compares it frame by frame")
    ap.add_argument("--out", default=CURTAIN, help="where the curtain's GIFs are written (default: curtain/)")
    ap.add_argument("--rows-out", default=ROWS, help="where the other lamps' GIFs are written (default: fleet/squid/)")
    a = ap.parse_args()

    ledmap = json.load(open(os.path.join(CURTAIN, "ledmap.json")))["map"]
    leds = [i for i, v in enumerate(ledmap) if v >= 0]
    rendered, bad = render(a.chrome, a.out), 0
    os.makedirs(a.rows_out, exist_ok=True)
    for key, r in rendered.items():
        name, out, cells = (NAMES[key], a.out, leds) if key in NAMES else (key, a.rows_out, range(r["w"] * r["h"]))
        raw, n, px = base64.b64decode(r["rgb"]), r["n"], r["w"] * r["h"]
        pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
        pixels = [c if max(c) >= BLACK_BELOW else (0, 0, 0) for c in pixels]
        if r["lampGamma"] == 1:
            # This lamp sends the file's values to the LEDs as they are: store what 2.8 gives the other lamps.
            pixels = [tuple(GAMMA_28[v] for v in c) for c in pixels]
        elif r["lampGamma"] != 2.8:
            sys.exit(f"{name}: no encoding for a lamp gamma of {r['lampGamma']}")
        count = Counter(pixels)
        count.pop((0, 0, 0), None)
        pal, index = median_cut([c + (k,) for c, k in count.items()], 255)
        pal = [(0, 0, 0)] + pal
        index = {c: i + 1 for c, i in index.items()}
        index[(0, 0, 0)] = 0
        frames = [bytes(index[c] for c in pixels[f * px:(f + 1) * px]) for f in range(n)]
        path = os.path.join(out, name + ".gif")
        with open(path, "wb") as f:
            f.write(gif(pal, frames, round(r["delay"] * 100), r["w"], r["h"]))
        lit = [max(c) >= (GAMMA_28[ON_LEVEL] if r["lampGamma"] == 1 else ON_LEVEL) for c in pal]
        on = [sum(lit[f[p]] for p in cells) / len(cells) for f in frames]
        check = "not decoded"
        if a.magick:
            got = subprocess.run([a.magick, path, "-coalesce", "-depth", "8", "rgb:-"], capture_output=True, timeout=120).stdout
            want = b"".join(bytes(pal[i]) for f in frames for i in f)
            check = "decodes to the rendered frames" if got == want else "DECODE MISMATCH"
            bad += got != want
        print(f"{name}.gif: {n} frames, {r['L']} s, {os.path.getsize(path)} bytes, "
              f"LEDs on {100 * sum(on) / n:.0f} % (min {100 * min(on):.0f}, max {100 * max(on):.0f}), {check}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
