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
        for slot, plan in mk.PLAN.items():
            pid, mode = plan[:2]; arg = plan[2] if len(plan) > 2 else None; span = plan[3] if len(plan) > 3 else (0, 255); boost = plan[4] if len(plan) > 4 else 1.0
            flat = [v for s in mk.build(PALX["palettes"][str(pid)], mode, arg, span, boost) for v in s]
            mk.lint(flat, f"palette{slot}.json")

    def test_residual_bounds(self):
        hue, _, _ = mk.residual(ANALOGOUS, mk.build(ANALOGOUS, "colorwaves"), "colorwaves")
        self.assertLess(hue, 14, "Colorwaves Analogous fit regressed")
        hue, _, _ = mk.residual(ANALOGOUS, mk.build(ANALOGOUS, "layer"), "layer")
        self.assertLess(hue, 14, "Palette-effect Analogous fit regressed")
        hue, _, _ = mk.residual(ANALOGOUS, mk.build(ANALOGOUS, "layer", "sine"), "layer", "sine")
        self.assertLess(hue, 14, "sine-dwell Analogous fit regressed")


class Dwell(unittest.TestCase):
    def test_flat_is_linear(self):
        self.assertEqual([mk.fork_phase(p, "flat") for p in (0, 64, 127)], [0, 128, 254])

    def test_sine_lingers_at_both_ends(self):
        phases = [mk.fork_phase(p, "sine") for p in range(128)]
        self.assertEqual(phases, sorted(phases))
        ends = sum(1 for t in phases if t < 32 or t >= 224); middle = sum(1 for t in phases if 96 <= t < 160)
        self.assertGreater(ends, 1.8 * middle, "arcsine: the ends get ~23 % each, the middle eighths ~8 %")

    def test_sine_palette_ends_on_the_forks_turning_colour(self):
        # Analogous ends on pure red (254,0,0); the sine fit lingers there, the flat fit averages it with orange
        sine = mk.build(ANALOGOUS, "layer", "sine")[7][1:]; flat = mk.build(ANALOGOUS, "layer", "flat")[7][1:]
        self.assertGreaterEqual(sine[0], 245); self.assertLessEqual(sine[2], 4)
        self.assertGreater(sine[0], flat[0])


class Head(unittest.TestCase):
    def test_black_hole_range_maps_slot_k_to_fork_index_k_upto_over_16(self):
        sunset = PALX["palettes"]["13"]; ent = mk.load16(sunset)
        head = mk.head(sunset, 40)
        self.assertEqual([s[0] for s in head], [16 * k for k in range(16)] + [255])
        self.assertEqual(head[8][1:], mk.cfp014(ent, 20))
        self.assertEqual(head[16][1:], mk.cfp014(ent, 40))
        self.assertTrue(all(s[3] == 0 for s in head), "the first 40/255 of Sunset has no blue")


if __name__ == "__main__":
    unittest.main()
