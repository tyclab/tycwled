"""The committed look GIFs: the size each lamp's Image effect plays unscaled, the frame count, looping, and never pale."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "curtain", "squid"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import mkgifs  # noqa: E402
import wledlab  # noqa: E402
from test_tycstation_fx import gif_decode  # noqa: E402

# file -> (width, height, frames, the lamp's colour gamma): the curtain's ledmap (its TycStation logo one still frame),
# the couch strip, a GLORB's raster, the Moon's matrix, an Exoy lamp's matrix (30 edges of 16 LEDs). A lamp at gamma
# 1.0 (the GLORBs) gets the 2.8 table's values in the file.
GIFS = {
    "curtain/squid-breathing.gif": (68, 42, 200, 2.8), "curtain/squid-ink.gif": (68, 42, 120, 2.8),
    "curtain/squid-deepsea.gif": (68, 42, 200, 2.8), "curtain/squid-eyes.gif": (68, 42, 200, 2.8),
    "curtain/squid-skin.gif": (68, 42, 120, 2.8), "curtain/squid-skin-water.gif": (68, 42, 128, 2.8),
    "curtain/tycstation.gif": (68, 42, 1, 2.8),
    "fleet/squid/squid-arms-300x1.gif": (300, 1, 40, 2.8), "fleet/squid/squid-arms-20x6.gif": (20, 6, 86, 1),
    "fleet/squid/squid-arms-8x8.gif": (8, 8, 40, 2.8), "fleet/squid/squid-arms-30x16.gif": (30, 16, 40, 2.8),
    "fleet/squid/tycstation-20x6.gif": (20, 6, 80, 1), "fleet/squid/tycstation-8x8.gif": (8, 8, 80, 2.8),
}
# Column 0 faces the wall behind both GLORBs and column 10, opposite it, the room (operator, 2026-11-24 test:
# "green atz wall directly behuind", "blue circles straight up front").
ROOM_COLUMN = 10
# A GLORB as it plays its arm waves (WLED 16.0.1): service() draws every 1000 / fps ms; the Image effect (image_loader.cpp,
# Speed 128) shows the next GIF frame on the first draw at least one GIF delay after the last; the bus scales each colour
# by the preset's brightness with color_fade(c, bri, video) (colors.cpp), which keeps the lowest bit of every channel
# above a quarter of the brightest + 1, so the brightest channel shows odd values only: one output step is 2.
GLORB_ARMS, ONE_STEP = "fleet/squid/squid-arms-20x6.gif", 2


def glorb_fade(colour, bri):
    top = (max(colour) >> 2) + 1
    return [((v * bri + 127) >> 8) | (v > top) for v in colour]


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
                shown = {frame[i:i + 3] for frame in gif_decode(read(path)) for i in range(0, len(frame), 3)}
                blues = [c for c in shown if c[2] > 240 and c[0] < c[1] < c[2]]
                self.assertTrue(blues, "the blue end is shown")
                ratio = min(c[0] / c[2] for c in blues)
                self.assertTrue(ratio < 0.12 if gamma == 1 else ratio > 0.25, ratio)

    def test_no_pixel_is_pale_on_its_lamp(self):
        # Operator, 2026-11-18: "no white except it is white really selected"; none of these looks selects white.
        for path, (_, _, _, gamma) in GIFS.items():
            with self.subTest(path=path):
                shown = {tuple(frame[i:i + 3]) for frame in gif_decode(read(path)) for i in range(0, len(frame), 3)}
                self.assertEqual(mkgifs.pale_entries(sorted(shown), gamma), [])

    def test_a_glorbs_front_display_faces_the_room(self):
        # The front display is the block of columns lit above half the brightest; the back mirrors it dimmed.
        for path in ("fleet/squid/squid-arms-20x6.gif", "fleet/squid/tycstation-20x6.gif"):
            with self.subTest(path=path):
                light = [0] * 20
                for frame in gif_decode(read(path)):
                    for i in range(0, len(frame), 3):
                        light[i // 3 % 20] += sum(frame[i:i + 3])
                lit = [x for x in range(20) if light[x] > max(light) / 2]
                self.assertEqual(lit, list(range(lit[0], lit[-1] + 1)), "one block, not round column 0")
                self.assertEqual((lit[0] + lit[-1]) / 2, ROOM_COLUMN)
        with open(os.path.join(ROOT, "curtain", "squid", "draw.js")) as f:
            front = re.search(r"ball: \{ front: (\d+),", f.read())
        self.assertEqual(int(front.group(1)), ROOM_COLUMN, "LOOK.ball.front in draw.js")

    def test_a_glorb_shows_every_arm_wave_frame_for_one_draw(self):
        # A delay above the draw time shows each frame for two or three draws, unevenly (50 ms on 23 ms: 46 or 69 ms).
        with open(os.path.join(ROOT, "glorb", "wled16-port", "cfg-overrides.json")) as f:
            fps = json.load(f)["hw"]["led"]["fps"]
        raw = read(GLORB_ARMS)
        delay = int.from_bytes(raw[raw.index(b"\x21\xF9\x04") + 4:][:2], "little") * 10
        self.assertLessEqual(delay, 1000 // fps)

    def test_no_glorb_led_moves_more_than_one_output_step_a_frame(self):
        # Every lit LED of the ledmap, each frame to the next and the last back to the first, at the brightness of each
        # preset that plays the file: no channel moves by more than one output step.
        with open(os.path.join(ROOT, "glorb", "wled16-port", "ledmap.json")) as f:
            leds = [i for i, v in enumerate(json.load(f)["map"]) if v >= 0]
        with open(os.path.join(ROOT, "fleet", "overlays", "glorb-presets.json")) as f:
            bris = {p["bri"] for p in json.load(f).values() if os.path.basename(GLORB_ARMS) in json.dumps(p)}
        frames = gif_decode(read(GLORB_ARMS))
        self.assertTrue(bris)
        for bri in bris:
            shown = [[glorb_fade(frame[3 * i:3 * i + 3], bri) for i in leds] for frame in frames]
            step = max(abs(a - b) for f in range(len(shown)) for p, q in zip(shown[f - 1], shown[f]) for a, b in zip(p, q))
            self.assertLessEqual(step, ONE_STEP, f"brightness {bri}")

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


if __name__ == "__main__":
    unittest.main()
