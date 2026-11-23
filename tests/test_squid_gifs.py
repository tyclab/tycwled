"""The committed look GIFs: the size each lamp's Image effect plays unscaled, animated, looping, and never pale."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "curtain", "squid"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import mkgifs  # noqa: E402
import wledlab  # noqa: E402
from test_tycstation_fx import gif_decode  # noqa: E402

# file -> (width, height, frames, the lamp's colour gamma): the curtain's ledmap, the couch strip, a GLORB's raster,
# the Moon's matrix, an Exoy lamp's matrix (30 edges of 16 LEDs), the cube's strip. A lamp at gamma 1.0 (the GLORBs,
# the cube) gets the 2.8 table's values in the file.
GIFS = {
    "curtain/squid-breathing.gif": (68, 42, 200, 2.8), "curtain/squid-ink.gif": (68, 42, 120, 2.8),
    "curtain/squid-deepsea.gif": (68, 42, 200, 2.8), "curtain/squid-eyes.gif": (68, 42, 200, 2.8),
    "curtain/squid-skin.gif": (68, 42, 120, 2.8), "curtain/squid-skin-water.gif": (68, 42, 128, 2.8),
    "curtain/tycstation.gif": (68, 42, 80, 2.8),
    "fleet/squid/squid-arms-300x1.gif": (300, 1, 40, 2.8), "fleet/squid/squid-arms-20x6.gif": (20, 6, 40, 1),
    "fleet/squid/squid-arms-8x8.gif": (8, 8, 40, 2.8), "fleet/squid/squid-arms-30x16.gif": (30, 16, 40, 2.8),
    "fleet/squid/squid-arms-288x1.gif": (288, 1, 40, 1),
    "fleet/squid/tycstation-300x1.gif": (300, 1, 80, 2.8), "fleet/squid/tycstation-20x6.gif": (20, 6, 80, 1),
    "fleet/squid/tycstation-8x8.gif": (8, 8, 80, 2.8), "fleet/squid/tycstation-30x16.gif": (30, 16, 80, 2.8),
    "fleet/squid/tycstation-288x1.gif": (288, 1, 80, 1),
}


def read(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return f.read()


class SquidGifs(unittest.TestCase):
    def test_every_loop_has_its_lamps_size_and_frame_count(self):
        for path, (width, height, frames, _) in GIFS.items():
            with self.subTest(path=path):
                raw = read(path)
                self.assertEqual((raw[:6], int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")),
                                 (b"GIF89a", width, height))
                self.assertEqual(wledlab.gif_frames(raw), frames)
                self.assertIn(b"NETSCAPE2.0\x03\x01\x00\x00\x00", raw, "loops forever")

    def test_the_gamma_one_files_hold_wire_values_and_the_others_hold_drawn_values(self):
        # The row's blue end is the mark's (90, 162, 255) at some level: drawn, its red is about a third of its blue;
        # after WLED's 2.8 table it is about a twentieth.
        for path, (_, _, _, gamma) in GIFS.items():
            if not path.startswith("fleet/squid/squid-arms-"):
                continue
            with self.subTest(path=path):
                raw = read(path)
                table = raw[13:13 + 3 * (2 << (raw[10] & 7))]
                blues = [table[i:i + 3] for i in range(0, len(table), 3) if table[i + 2] > 240 and table[i] < table[i + 1] < table[i + 2]]
                self.assertTrue(blues, "the blue end is in the colour table")
                ratio = min(c[0] / c[2] for c in blues)
                self.assertTrue(ratio < 0.12 if gamma == 1 else ratio > 0.25, ratio)

    def test_no_pixel_is_pale_on_its_lamp(self):
        # Operator, 2026-11-18: "no white except it is white really selected"; none of these looks selects white.
        for path, (_, _, _, gamma) in GIFS.items():
            with self.subTest(path=path):
                shown = {tuple(frame[i:i + 3]) for frame in gif_decode(read(path)) for i in range(0, len(frame), 3)}
                self.assertEqual(mkgifs.pale_entries(sorted(shown), gamma), [])

    def test_the_check_finds_white_lavender_and_a_pale_wire_value(self):
        self.assertEqual(mkgifs.pale_entries([(0, 0, 0), (255, 255, 255), (180, 140, 245), (90, 162, 255)], 2.8),
                         [(255, 255, 255), (180, 140, 245)])
        lavender = tuple(mkgifs.GAMMA_28[v] for v in (180, 140, 245))
        self.assertEqual(mkgifs.pale_entries([lavender, (14, 72, 255)], 1), [lavender])

    def test_the_floor_keeps_the_websites_tokens_and_lifts_their_mixes(self):
        for token in ((90, 162, 255), (139, 108, 240), (255, 74, 61)):
            self.assertEqual(mkgifs.vivid(token), token)
        violet_to_red = (174, 98, 186)  # 30 % of the way, mixed channel by channel as canvas and CSS do
        self.assertTrue(mkgifs.pale(violet_to_red))
        self.assertFalse(mkgifs.pale(mkgifs.vivid(violet_to_red)))

    def test_no_other_gif_is_committed_unlisted(self):
        found = {os.path.relpath(os.path.join(folder, name), ROOT)
                 for folder in (os.path.join(ROOT, "curtain"), os.path.join(ROOT, "fleet", "squid"))
                 for name in os.listdir(folder) if name.endswith(".gif")}
        self.assertEqual(found, set(GIFS))


if __name__ == "__main__":
    unittest.main()
