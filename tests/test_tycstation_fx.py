"""usermods/tycstation_fx: effect metadata, the palette, the gamma seam, and the patterns rendered on the host.

The render tests compile tests/tycstation_fx_host.cpp, which runs the usermod's own tycstation_core.h, and compare it
with the committed squid GIFs that the same drawings (curtain/squid/draw.js) produced. They skip without a C++ compiler.
"""
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UM = os.path.join(ROOT, "usermods", "tycstation_fx")

CPP = open(os.path.join(UM, "tycstation_fx.cpp")).read()
CORE = open(os.path.join(UM, "tycstation_core.h")).read()
DRAW = open(os.path.join(ROOT, "curtain", "squid", "draw.js")).read()
# The mark's colours and where its violet sits, as the drawings hold them.
BLUE, VIOLET, RED = (tuple(json.loads(c)) for c in re.search(r"const B = (\[.*?\]), V = (\[.*?\]), R = (\[.*?\])", DRAW).groups())
KNEE = float(re.search(r"u < (\.\d+) \? mix\(B, V,", DRAW).group(1))
# The palette: the gradient out to red over its first half, mirrored back to blue over the second, so an effect that
# runs round the palette meets no seam.
STOPS = [(0, BLUE), (round(KNEE * 128), VIOLET), (128, RED), (256 - round(KNEE * 128), VIOLET), (255, BLUE)]
# WLED 16's output table for gamma 2.8 (colors.cpp calcGammaTable).
T28 = [int((i / 255) ** 2.8 * 255 + 0.5) for i in range(256)]


def c_array(name):
    body = re.search(r"\b%s\[\d+\] = \{(.*?)\};" % name, CORE, re.S).group(1)
    return [int(v) for v in re.findall(r"\d+", body)]


def gif_decode(raw):
    """Frames of a GIF as mkgifs.py writes them (global table, whole frames) -> [bytes of RGB]."""
    w, h, flags = int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little"), raw[10]
    size = 3 * (2 << (flags & 7))
    table, pos, frames = raw[13:13 + size], 13 + size, []
    while raw[pos] != 0x3B:
        if raw[pos] == 0x21:
            pos += 2
            while raw[pos]:
                pos += raw[pos] + 1
            pos += 1
            continue
        assert raw[pos] == 0x2C and not raw[pos + 9] & 0x80, "whole frames on the global table only"
        mcs, pos, data = raw[pos + 10], pos + 11, bytearray()
        while raw[pos]:
            data += raw[pos + 1:pos + 1 + raw[pos]]
            pos += raw[pos] + 1
        pos += 1
        clear, out, acc, bits, size_, dic, prev = 1 << mcs, bytearray(), 0, 0, mcs + 1, None, None
        for byte in data:
            acc |= byte << bits
            bits += 8
            while bits >= size_:
                code, acc, bits = acc & ((1 << size_) - 1), acc >> size_, bits - size_
                if code == clear:
                    dic, size_, prev = [bytes([i]) for i in range(clear)] + [b"", b""], mcs + 1, None
                    continue
                if code == clear + 1:
                    break
                entry = dic[code] if code < len(dic) else dic[prev] + dic[prev][:1]
                if prev is not None:
                    dic.append(dic[prev] + entry[:1])
                    if len(dic) == 1 << size_ and size_ < 12:
                        size_ += 1
                out += entry
                prev = code
        frames.append(b"".join(table[3 * i:3 * i + 3] for i in out[:w * h]))
    return frames


class Metadata(unittest.TestCase):
    def fxdata(self, name):
        m = re.search(r'PROGMEM = "(%s@[^"]*)"' % re.escape(name), CPP)
        self.assertIsNotNone(m, name)
        return m.group(1).split(";")

    def test_the_three_effects_and_their_sliders(self):
        want = {"Squid Arms": ("!,Sound,Waves", "c1=64"), "Squid Skin": ("!,Sound,Cell size", "c1=85"),
                "Squid Plankton": ("!,Sound,Specks", "c1=32")}
        for name, (sliders, c1) in want.items():
            with self.subTest(name=name):
                head, colours, palette, flags, defaults = self.fxdata(name)
                self.assertEqual(head, f"{name}@{sliders}")
                self.assertEqual((colours, palette), ("", "!"), "no colour slots, the palette selectable")
                self.assertEqual(flags, "12v", "1D and 2D, volume reactive")
                self.assertEqual(defaults.split(","), ["sx=128", "ix=192", c1, "pal=0"])

    def test_effects_register_at_boot_assigned_ids(self):
        self.assertEqual(len(re.findall(r"strip\.addEffect\(255, ", CPP)), 3)

    def test_palette_is_registered_by_name(self):
        self.assertIn('kName[] PROGMEM = "TycStation"', CPP)
        self.assertIn("usermodPalettes.insert(usermodPalettes.begin()", CPP)


class Palette(unittest.TestCase):
    def test_stops_are_the_drawings_gradient_out_and_back(self):
        self.assertEqual(c_array("kStops"), [v for at, colour in STOPS for v in (at, *colour)])

    def test_gamma_table_is_wleds_28(self):
        self.assertEqual(c_array("kGamma28"), T28)

    def test_a_float_table_rounds_the_same(self):
        # The lamps build their 2.8 table with powf (colors.cpp calcGammaTable). Every entry sits further from a rounding
        # edge than 8 float32 ulps at full scale, so that table equals this one.
        edge = min(abs(x - round(x)) for x in ((i / 255) ** 2.8 * 255 + 0.5 for i in range(1, 256)))
        self.assertGreater(edge, 255 * 2 ** -20)


@unittest.skipUnless(shutil.which("c++"), "no C++ compiler on PATH")
class Host(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.exe = os.path.join(cls.tmp, "host")
        src = os.path.join(ROOT, "tests", "tycstation_fx_host.cpp")
        base = ["c++", "-std=c++17", "-O1", "-Wall", "-Werror", "-o", cls.exe, src]
        if subprocess.run(base[:3] + ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"] + base[3:],
                          capture_output=True).returncode:
            subprocess.run(base, check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def render(self, fx, w, h, t0, dt, frames, gamma=True, strength=1.0, slider=None):
        slider = {"arms": 64, "skin": 85, "plankton": 32}[fx] if slider is None else slider
        out = subprocess.run([self.exe, fx, str(w), str(h), str(t0), str(dt), str(frames), "1" if gamma else "0",
                              str(strength), str(slider)], capture_output=True, check=True).stdout
        n = w * h * 3
        self.assertEqual(len(out), n * frames)
        return [out[i * n:(i + 1) * n] for i in range(frames)]

    def test_palette_bytes_follow_the_lamps_colour_gamma(self):
        # A lamp with colour gamma on gets the stops as drawn and applies its table itself; with it off (the GLORBs)
        # the colours go through the 2.8 table here, the positions stay.
        for gamma, encode in ((1, lambda v: v), (0, lambda v: T28[v])):
            with self.subTest(gamma=gamma):
                got = list(subprocess.run([self.exe, "palette", str(gamma)], capture_output=True, check=True).stdout)
                self.assertEqual(got, [v for at, colour in STOPS for v in (at, *map(encode, colour))])

    def test_gamma_off_puts_a_28_lamps_values_on_the_wire(self):
        for fx, w, h in (("arms", 20, 6), ("skin", 68, 42), ("plankton", 20, 6), ("plankton", 300, 1)):
            with self.subTest(fx=fx, size=(w, h)):
                for on, off in zip(self.render(fx, w, h, 0.3, 0.7, 6), self.render(fx, w, h, 0.3, 0.7, 6, gamma=False)):
                    self.assertEqual(off, bytes(T28[v] for v in on))

    def assertFramesAlign(self, got, want, select=lambda frame: frame, encoded=False):
        # each rendered frame is closest to the drawing's frame of the same time, on the wire of a 2.8 lamp
        table = range(256) if encoded else T28
        wire = [[table[v] for v in select(f)] for f in want]
        for i, frame in enumerate(got):
            mine = [table[v] for v in select(frame)]
            dist = [sum(abs(a - b) for a, b in zip(mine, other)) for other in wire]
            self.assertEqual(dist.index(min(dist)), i, f"frame {i}")

    def test_arms_are_draw_js_arm_waves(self):
        # armWaves() in doubles: the gradient (stops 0, 61, 128 of the palette) at the wave's level over black
        def level(x, w, t):
            k = 2 * math.pi * (2 if w >= 16 else 1) / (w / 2)
            return .08 + .92 * (.5 + .5 * math.sin(abs(x - (w - 1) / 2) * k - math.pi * t)) ** 3

        def gradient(u):
            stops = STOPS[:3]
            p = u * 128
            (a, ca), (b, cb) = (stops[0], stops[1]) if p < 61 else (stops[1], stops[2])
            return [ca[c] + (cb[c] - ca[c]) * (p - a) / (b - a) for c in range(3)]

        for w, h in ((300, 1), (20, 6), (8, 8)):
            with self.subTest(size=(w, h)):
                for i, frame in enumerate(self.render("arms", w, h, 0, 0.13, 15)):
                    want = [round(v * level(x, w, i * 0.13)) for y in range(h) for x in range(w) for v in gradient(x / (w - 1))]
                    self.assertLessEqual(max(abs(a - b) for a, b in zip(frame, want)), 1)

    def test_arms_follow_the_committed_gifs(self):
        # The 20x6 file holds wire values (the GLORBs run gamma 1.0), so its gamma-off render is compared as it is.
        for path, w, h in (("squid-arms-300x1.gif", 300, 1), ("squid-arms-8x8.gif", 8, 8), ("squid-arms-20x6.gif", 20, 6)):
            with self.subTest(path=path), open(os.path.join(ROOT, "fleet", "squid", path), "rb") as f:
                want, glorb = gif_decode(f.read()), w == 20
                self.assertFramesAlign(self.render("arms", w, h, 0, 0.05, len(want), gamma=not glorb), want, encoded=glorb)

    def test_skin_follows_the_committed_gif_where_the_squid_is_absent(self):
        # squid-skin.gif draws the squid from 2.6 s to 10.6 s of its 12; before and after, the frames are the skin alone
        with open(os.path.join(ROOT, "curtain", "squid-skin.gif"), "rb") as f:
            want = gif_decode(f.read())
        frames = [i for i in range(len(want)) if i * 0.1 < 2.55 or i * 0.1 > 10.65]
        got = {i: self.render("skin", 68, 42, i * 0.1, 0.1, 1)[0] for i in frames}
        self.assertFramesAlign([got[i] for i in frames], [want[i] for i in frames])

    def test_plankton_follows_the_committed_gif_above_the_school(self):
        # squid-deepsea.gif: from 13.2 s the squid has left the frame; the school swims below row 25
        with open(os.path.join(ROOT, "curtain", "squid-deepsea.gif"), "rb") as f:
            want = gif_decode(f.read())
        frames = [i for i in range(len(want)) if i * 0.08 > 13.25]
        got = [self.render("plankton", 68, 42, i * 0.08, 0.08, 1)[0] for i in frames]
        self.assertFramesAlign(got, [want[i] for i in frames], select=lambda fr: fr[:68 * 24 * 3])

    def test_silence_lowers_the_pulse_and_keeps_moving(self):
        for fx, w, h in (("arms", 300, 1), ("skin", 68, 42), ("plankton", 68, 42)):
            with self.subTest(fx=fx):
                full, quiet = self.render(fx, w, h, 1, 0.5, 4), self.render(fx, w, h, 1, 0.5, 4, strength=0.5)
                self.assertLess(sum(map(sum, quiet)), sum(map(sum, full)))
                self.assertEqual(len(set(quiet)), 4, "every frame differs")

    def test_any_segment_size(self):
        for fx in ("arms", "skin", "plankton"):
            for w, h in ((1, 1), (2, 1), (7, 3), (8, 8), (20, 6), (60, 16), (68, 42), (300, 1), (3, 40)):
                for slider in (0, 255):
                    with self.subTest(fx=fx, size=(w, h), slider=slider):
                        frames = self.render(fx, w, h, 0, 1.3, 10, slider=slider)
                        self.assertTrue(any(map(any, frames)), "lights something")


if __name__ == "__main__":
    unittest.main()
