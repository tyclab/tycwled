"""Compile the actual GLORB color_add helper against original-instruction vectors.

Black Hole, Frizzles and Tartan add pixels through the original color_add at
0x42026220 with fast=0. The 31 vectors were selected from 2,048 calls of
that routine in Ghidra 12.0.4 (edge sums and xorshift32 pairs); capture SHA256
a8e36f83415aafb3494e54cc617aedfadf9007f09719dd3c0fc257a9ae0e8259.
These are helper regressions, not whole-firmware acceptance.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "glorb/usermod/glorb_fx/glorb_fx.cpp"
VECTORS = [
    (0x0000ff, 0x000000, 0x0000ff),
    (0x0001ff, 0x010000, 0x0101ff),
    (0x0002ff, 0x020000, 0x0202ff),
    (0x007fff, 0x7f0000, 0x7f7fff),
    (0xbd014f, 0x288475, 0xe585c4),
    (0x01fffe, 0xff0101, 0xfffffe),
    (0x02fefd, 0xfe0202, 0xfffffe),
    (0x02fffd, 0xff0202, 0xfffffd),
    (0x7f8180, 0x817f7f, 0xfffffe),
    (0x7fc880, 0xc87f7f, 0xffffc6),
    (0x7ffe80, 0xfe7f7f, 0xffffaa),
    (0x7fff80, 0xff7f7f, 0xffffaa),
    (0x80c87f, 0xc88080, 0xffffc6),
    (0x80fe7f, 0xfe8080, 0xffffaa),
    (0x80ff7f, 0xff8080, 0xffffa9),
    (0x81817e, 0x818181, 0xfffffc),
    (0x81c87e, 0xc88181, 0xffffc5),
    (0x81fe7e, 0xfe8181, 0xffffa9),
    (0x81ff7e, 0xff8181, 0xffffa9),
    (0xc87f37, 0x7fc8c8, 0xffffc6),
    (0xc88037, 0x80c8c8, 0xffffc6),
    (0xc88137, 0x81c8c8, 0xffffc5),
    (0xc8c837, 0xc8c8c8, 0xffffa2),
    (0x28df91, 0x008e2d, 0x1bff84),
    (0x93699b, 0x4da83b, 0xd1ffc7),
    (0x0e164e, 0x769de8, 0x6c93ff),
    (0x0c7f78, 0xda0d8e, 0xdf88ff),
    (0x7db562, 0xf7c4e5, 0xfbffdd),
    (0xbdc2fb, 0x32adb3, 0x8dd9ff),
    (0x80ff14, 0x8df639, 0x88ff27),
    (0xeaeea7, 0x0965b6, 0xb1f7ff),
]


def function(source, name):
    match = re.search(r"^static[^\n]*\b" + name + r"\([^\n]*\)\s*\{", source, re.M)
    if match is None:
        raise AssertionError("missing actual helper: " + name)
    depth, end = 1, match.end()
    while depth and end < len(source):
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    if depth:
        raise AssertionError("incomplete actual helper: " + name)
    return source[match.start():end]


PRELUDE = r"""
#include <cstdint>
#include <iostream>
#define R(c) uint8_t(uint32_t(c)>>16)
#define G(c) uint8_t(uint32_t(c)>>8)
#define B(c) uint8_t(uint32_t(c))
#define W(c) uint8_t(uint32_t(c)>>24)
#define RGBW32(r,g,b,w) ((uint32_t(w)<<24)|(uint32_t(r)<<16)|(uint32_t(g)<<8)|uint32_t(b))
"""
MAIN = r"""
int main() {
  uint32_t a,b;
  while(std::cin>>a>>b) std::cout<<glorb_color_add(a,b)<<'\n';
  return std::cin.eof()?0:2;
}
"""


class Routing(unittest.TestCase):
    def test_adding_effects_use_the_original_add(self):
        source = SOURCE.read_text()
        wrapper = function(source, "glorb_addPixelColorXY")
        self.assertIn("glorb_color_add(", wrapper)
        self.assertNotIn("addPixelColorXY(x", wrapper.split("{", 1)[1])
        for name in ("blackhole", "frizzles", "tartan"):
            with self.subTest(effect=name):
                body = function(source, "glorb_mode_" + name)
                self.assertIn("glorb_addPixelColorXY(", body)
                self.assertNotRegex(body, r"SEGMENT\.addPixelColor")


@unittest.skipUnless(shutil.which("c++"), "no C++ compiler on PATH")
class Arithmetic(unittest.TestCase):
    def render(self, replacement=None):
        helper = function(SOURCE.read_text(), "glorb_color_add")
        if replacement:
            old, new = replacement
            self.assertIn(old, helper)
            helper = helper.replace(old, new, 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "oracle.cpp").write_text(PRELUDE + helper + MAIN)
            subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                            str(root / "oracle.cpp"), "-o", str(root / "oracle")],
                           capture_output=True, check=True, timeout=60)
            inputs = "".join(f"{a} {b}\n" for a, b, _ in VECTORS)
            result = subprocess.run([str(root / "oracle")], input=inputs, text=True,
                                    capture_output=True, check=True, timeout=10)
            return [int(line) for line in result.stdout.splitlines()]

    def test_original_captured_vectors(self):
        self.assertEqual(self.render(), [row[2] for row in VECTORS])

    def test_control_wled16_ratio_preserving_add_fails(self):
        wled16 = ("return RGBW32(r * 255 / top, g * 255 / top, b * 255 / top, w * 255 / top);",
                  "const uint32_t s = (255u << 8) / top;\n"
                  "  return RGBW32((r * s) >> 8, (g * s) >> 8, (b * s) >> 8, (w * s) >> 8);")
        self.assertNotEqual(self.render(wled16), [row[2] for row in VECTORS])

    def test_control_saturating_add_fails(self):
        saturate = ("return RGBW32(r * 255 / top, g * 255 / top, b * 255 / top, w * 255 / top);",
                    "return RGBW32(r > 255 ? 255 : r, g > 255 ? 255 : g, b > 255 ? 255 : b, w > 255 ? 255 : w);")
        self.assertNotEqual(self.render(saturate), [row[2] for row in VECTORS])
