"""Palette emulation against values the firmware produces (see glorb/mkpalettes.py)."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "glorb"))
import mkpalettes as mk  # noqa: E402

PALX = json.load(open(os.path.join(HERE, "..", "glorb", "factory-0.14.4-GLORB.1.3", "palx.json")))
ANALOGOUS = PALX["palettes"]["18"]


class Loader(unittest.TestCase):
    def test_analogous_slots_match_fastled_forcing(self):
        # 5 stops (< 16) → each stop forced into its own slot, duplicates where stops share a slot pair
        slots = [tuple(s) for s in mk.load16(ANALOGOUS)]
        self.assertEqual(slots[0], (3, 0, 255))
        # 16.16 fixed-point fill truncates: the last slot of a 3-step ramp to 255 lands on 254, as on the lamp
        self.assertEqual(slots[15], (254, 0, 0))
        self.assertEqual(slots[11], slots[12], "stop at index 191 is held for two slots")

    def test_seventeen_stops_are_unforced(self):
        stops = [[16 * k, k, k, k] for k in range(16)] + [[255, 15, 15, 15]]
        self.assertEqual([s[0] for s in mk.load16(stops)], list(range(16)))


class Blend(unittest.TestCase):
    def test_wled16_nowrap_remaps_by_240_over_256(self):
        ent = [[16 * k, 0, 0] for k in range(16)]
        self.assertEqual(mk.cfp16(ent, 255, True)[0], 16 * 14 + ((15 << 4) * 16 >> 8))
        self.assertEqual(mk.cfp16(ent, 0, True), [0, 0, 0])

    def test_wled16_linearblend_wraps_at_slot_15(self):
        ent = [[16 * k, 0, 0] for k in range(16)]
        self.assertEqual(mk.cfp16(ent, 255, False)[0], (240 * 16 + 0 * 240) >> 8)

    def test_fastled_scale8_fixed(self):
        ent = [[255, 0, 0]] * 16
        self.assertEqual(mk.cfp014(ent, 200), [255, 0, 0])


class Fit(unittest.TestCase):
    def test_generated_palettes_respect_wled_limits(self):
        for slot, (pid, mode) in mk.PLAN.items():
            flat = [v for s in mk.build(PALX["palettes"][str(pid)], mode) for v in s]
            mk.lint(flat, f"palette{slot}.json")

    def test_residual_bounds(self):
        hue, _, _ = mk.residual(ANALOGOUS, mk.build(ANALOGOUS, "colorwaves"), "colorwaves")
        self.assertLess(hue, 12, "Colorwaves Analogous fit regressed")
        hue, _, _ = mk.residual(ANALOGOUS, mk.build(ANALOGOUS, "layer"), "layer")
        self.assertLess(hue, 12, "Palette-effect Analogous fit regressed")


if __name__ == "__main__":
    unittest.main()
