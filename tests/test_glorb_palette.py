"""Compile the actual GLORB palette helper against original-instruction vectors.

The 26 vectors use authored palettes, not firmware bytes. They were selected from
21,504 original ColorFromPalette calls in Ghidra12.0.4; capture SHA256
8ce8476f9671310f3a2ee567382e2a3ac125e7c873ad8ce9af85fa32195e63b2.
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
    (3, 255, 1, 1, (32, 89, 162)),
    (3, 255, 1, 2, (46, 87, 160)),
    (3, 255, 1, 15, (225, 56, 130)),
    (3, 255, 1, 16, (238, 55, 128)),
    (3, 255, 1, 31, (203, 19, 93)),
    (3, 255, 1, 127, (222, 53, 127)),
    (3, 255, 1, 239, (218, 51, 123)),
    (3, 255, 1, 240, (232, 49, 122)),
    (3, 255, 1, 254, (45, 86, 160)),
    (3, 255, 1, 255, (31, 89, 162)),
    (3, 0, 1, 15, (0, 0, 0)),
    (3, 1, 1, 15, (2, 0, 1)),
    (3, 127, 1, 15, (113, 28, 65)),
    (3, 253, 1, 15, (224, 55, 129)),
    (3, 254, 1, 15, (225, 56, 130)),
    (3, 255, 0, 15, (19, 92, 165)),
    (3, 255, 0, 255, (232, 49, 122)),
    (3, 255, 2, 239, (13, 86, 159)),
    (3, 255, 2, 240, (27, 83, 157)),
    (3, 255, 2, 255, (218, 51, 123)),
    (2, 254, 1, 1, (16, 239, 16)),
    (2, 254, 1, 15, (240, 15, 239)),
    (2, 254, 1, 255, (15, 240, 15)),
    (1, 1, 1, 3, (2, 2, 2)),
    (1, 254, 1, 3, (255, 255, 255)),
    (1, 255, 1, 3, (255, 255, 255)),

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
#include <array>
#include <cstdint>
#include <iostream>
#define R(c) uint8_t(uint32_t(c)>>16)
#define G(c) uint8_t(uint32_t(c)>>8)
#define B(c) uint8_t(uint32_t(c))
#define RGBW32(r,g,b,w) ((uint32_t(w)<<24)|(uint32_t(r)<<16)|(uint32_t(g)<<8)|uint32_t(b))
enum TBlendType { NOBLEND, LINEARBLEND, LINEARBLEND_NOWRAP };
std::array<uint32_t,16> palette;
#define SEGPALETTE palette
"""
MAIN = r"""
int main() {
  unsigned kind,bri,blend,index;
  while(std::cin>>kind>>bri>>blend>>index) {
    const unsigned extremes[] = {0,255,1,255,0,254};
    unsigned raw[48];
    for(unsigned i=0;i<48;i++)
      raw[i]=kind==1?255:kind==2?extremes[i%6]:(i*73+19)%256;
    for(unsigned i=0;i<16;i++) palette[i]=RGBW32(raw[3*i],raw[3*i+1],raw[3*i+2],0);
    const uint32_t c=glorb_palette_color(index,bri,TBlendType(blend));
    std::cout<<unsigned(R(c))<<' '<<unsigned(G(c))<<' '<<unsigned(B(c))<<'\n';
  }
  return std::cin.eof()?0:2;
}
"""


class Routing(unittest.TestCase):
    def test_all_six_effects_use_the_legacy_helper(self):
        source = SOURCE.read_text()
        for name in ("hiphotic", "blackhole", "frizzles", "colorwaves", "running", "tartan"):
            with self.subTest(effect=name):
                body = function(source, "glorb_mode_" + name)
                self.assertRegex(body, r"glorb_(?:palette_color|color_from_palette)\(")
                self.assertNotRegex(body, r"(?:SEGMENT\.color_from_palette|ColorFromPalette)\(")


@unittest.skipUnless(shutil.which("c++"), "no C++ compiler on PATH")
class Arithmetic(unittest.TestCase):
    def render(self, replacement=None):
        source = SOURCE.read_text()
        helpers = function(source, "glorb_scale8") + "\n" + function(source, "glorb_palette_color")
        if replacement:
            old, new = replacement
            self.assertIn(old, helpers)
            helpers = helpers.replace(old, new, 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "oracle.cpp").write_text(PRELUDE + helpers + MAIN)
            subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                            str(root / "oracle.cpp"), "-o", str(root / "oracle")],
                           capture_output=True, check=True, timeout=60)
            inputs = "".join(" ".join(map(str, row[:4])) + "\n" for row in VECTORS)
            result = subprocess.run([str(root / "oracle")], input=inputs, text=True,
                                    capture_output=True, check=True, timeout=10)
            return [tuple(map(int, line.split())) for line in result.stdout.splitlines()]

    def test_original_captured_vectors(self):
        self.assertEqual(self.render(), [row[4] for row in VECTORS])

    def test_controls_detect_combined_rounding_brightness_and_wrap_changes(self):
        mutations = [
            ("glorb_scale8(channels[i], 255 - fraction) + glorb_scale8(second[i], fraction)",
             "((channels[i] * (256 - fraction) + second[i] * fraction) >> 8)"),
            ("glorb_scale8(channels[i], brightness + 1)", "glorb_scale8(channels[i], brightness)"),
            ("uint16_t(index) * 240", "uint16_t(index) * 241"),
        ]
        for mutation in mutations:
            with self.subTest(change=mutation[0]):
                self.assertNotEqual(self.render(mutation), [row[4] for row in VECTORS])
