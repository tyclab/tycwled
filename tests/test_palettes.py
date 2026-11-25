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


class Verbatim(unittest.TestCase):
    def test_every_generated_palette_is_the_factory_stops_unchanged(self):
        for slot, (_fn, body, pid, _name) in mk.build().items():
            factory = [v for stop in PALX["palettes"][str(pid)] for v in stop]
            self.assertEqual(body["palette"], factory,
                             f"palette{slot} (factory {pid}) is not the factory stops verbatim")


class Ids(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
