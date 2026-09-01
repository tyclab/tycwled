"""The port's palettes must be the factory's palettes, byte for byte.

WLED re-encoded most of its built-in gradient palettes after 0.14, so the same palette ID no
longer holds the same colours (see glorb/experiments/2026-08-31-reversing/NOTES.md section 11).
The port therefore ships the factory stops as custom palettes and points every preset at those.
These tests guard that promise: no re-encoding, no fitting, and no preset left pointing at a
built-in ID.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "glorb"))
import mkpalettes as mk  # noqa: E402

PALX = json.load(open(os.path.join(HERE, "..", "glorb", "factory-0.14.4-GLORB.1.3", "palx.json")))
PRESETS = json.load(open(os.path.join(HERE, "..", "glorb", "wled16-port", "presets.json")))
PORT = os.path.join(HERE, "..", "glorb", "wled16-port")


class Verbatim(unittest.TestCase):
    def test_every_generated_palette_is_the_factory_stops_unchanged(self):
        for slot, (_fn, body, pid, _name) in mk.build().items():
            factory = [v for stop in PALX["palettes"][str(pid)] for v in stop]
            self.assertEqual(body["palette"], factory,
                             f"palette{slot} (factory {pid}) is not the factory stops verbatim")

    def test_committed_files_match_the_generator(self):
        for slot, (fn, body, _pid, _name) in mk.build().items():
            with open(os.path.join(PORT, fn)) as f:
                self.assertEqual(json.load(f), body, f"{fn} is stale -- rerun mkpalettes.py")

    def test_atlantica_is_the_one_wled_left_alone(self):
        # documents why Running - Atlantica was the only preset matching before the palettes were fixed
        wled16_atlantica = [0, 0, 28, 112, 50, 32, 96, 255, 100, 0, 243, 45,
                            150, 12, 95, 82, 200, 25, 190, 95, 255, 40, 170, 80]
        factory = [v for stop in PALX["palettes"]["51"] for v in stop]
        self.assertEqual(factory, wled16_atlantica)


class Ids(unittest.TestCase):
    def test_custom_ids_count_down_from_200(self):
        self.assertEqual([mk.custom_id(s) for s in range(6)], [200, 199, 198, 197, 196, 195])

    def test_slots_are_contiguous_from_zero(self):
        # WLED stops scanning after a gap in palette<N>.json, so a hole would silently drop palettes
        self.assertEqual(sorted(mk.PLAN), list(range(len(mk.PLAN))))


class Presets(unittest.TestCase):
    def test_every_preset_points_at_a_custom_palette(self):
        custom = {mk.custom_id(s) for s in mk.PLAN}
        for key, preset in PRESETS.items():
            for seg in preset.get("seg", []) if isinstance(preset, dict) else []:
                if seg.get("fx") is None:
                    continue
                self.assertIn(seg["pal"], custom,
                              f"preset {key} uses palette {seg['pal']}: a built-in ID is re-encoded in WLED 16")

    def test_the_plan_covers_exactly_the_palettes_the_factory_presets_use(self):
        factory = json.load(open(os.path.join(HERE, "..", "glorb", "factory-0.14.4-GLORB.1.3", "presets.json")))
        used = {seg["pal"] for p in factory.values() if isinstance(p, dict)
                for seg in p.get("seg", []) if seg.get("fx") is not None}
        self.assertEqual(set(mk.PLAN.values()), used)


class Limits(unittest.TestCase):
    def test_stops_stay_within_what_wled_accepts(self):
        for slot, (_fn, body, pid, _name) in mk.build().items():
            flat = body["palette"]
            self.assertEqual(len(flat) % 4, 0, f"palette{slot}: not whole 4-byte stops")
            self.assertLessEqual(len(flat) // 4, 18, f"palette{slot}: WLED reads at most 18 stops")
            self.assertEqual(flat[0], 0, f"palette{slot} (factory {pid}) must start at index 0")
            self.assertEqual(flat[-4], 255, f"palette{slot} (factory {pid}) must end at index 255")
            self.assertTrue(all(0 <= v <= 255 for v in flat), f"palette{slot}: value outside 0..255")

    def test_indices_are_strictly_increasing(self):
        for slot, (_fn, body, _pid, _name) in mk.build().items():
            idx = body["palette"][0::4]
            self.assertEqual(idx, sorted(set(idx)), f"palette{slot}: stop indices must ascend")


if __name__ == "__main__":
    unittest.main()
