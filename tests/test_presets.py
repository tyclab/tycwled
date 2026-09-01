"""The port's presets must be the factory's presets, field for field.

The palettes drifted once because a fitted approximation stood in for the factory bytes and the
gate had been calibrated against the approximation (NOTES.md section 11). The presets carry the
same risk: every speed, intensity, floor and segment layout was once tuned against the broken
measurement chain. These tests pin them to the factory presets verbatim, allowing exactly two
translations — the effect ID (fork effect -> glorb_fx usermod effect) and the palette ID
(re-encoded built-in -> verbatim custom slot). Anything else differing is a regression, not a fit.
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "glorb"))
import mkpalettes as mk  # noqa: E402

FACTORY = json.load(open(os.path.join(HERE, "..", "glorb", "factory-0.14.4-GLORB.1.3", "presets.json")))
PORT = json.load(open(os.path.join(HERE, "..", "glorb", "wled16-port", "presets.json")))

# the only two fields a segment may differ in, and why
TRANSLATED = {"fx", "pal"}


def effect_segments(preset):
    return [s for s in preset.get("seg", []) if s.get("stop") != 0]


class Verbatim(unittest.TestCase):
    def test_same_preset_slots(self):
        self.assertEqual(sorted(FACTORY), sorted(PORT), "preset slots differ from the factory file")

    def test_toplevel_fields_are_factory_verbatim(self):
        for k, f in FACTORY.items():
            if not isinstance(f, dict) or not f:
                continue
            p = PORT[k]
            self.assertEqual({x: v for x, v in f.items() if x != "seg"},
                             {x: v for x, v in p.items() if x != "seg"},
                             f"preset {k}: top-level fields differ from factory")

    def test_segments_are_factory_verbatim_except_fx_and_pal(self):
        for k, f in FACTORY.items():
            if not isinstance(f, dict) or not f:
                continue
            p = PORT[k]
            self.assertEqual(len(f["seg"]), len(p["seg"]), f"preset {k}: segment count differs")
            for n, (fs, ps) in enumerate(zip(f["seg"], p["seg"])):
                self.assertEqual({x: v for x, v in fs.items() if x not in TRANSLATED},
                                 {x: v for x, v in ps.items() if x not in TRANSLATED},
                                 f"preset {k} seg {n}: fields beyond fx/pal differ from factory")


class Effects(unittest.TestCase):
    def test_presets_only_use_effects_the_map_names(self):
        # effects.json is what install asserts against /json/eff; if a preset uses an fx that is
        # not in it, a WLED renumbering could point that preset at a stock effect unnoticed
        effects = json.load(open(os.path.join(HERE, "..", "glorb", "wled16-port", "effects.json")))
        known = {int(k) for k in effects}
        used = {s["fx"] for p in PORT.values() if isinstance(p, dict) for s in effect_segments(p)}
        self.assertEqual(used, known, "presets.json and effects.json disagree about the effect IDs")

    def test_every_preset_runs_the_effect_its_name_promises(self):
        # injectivity alone lets two effect IDs swap and stay green; the factory names every preset
        # "<Effect> - <Palette>", so the ID must resolve to that effect by name
        effects = json.load(open(os.path.join(HERE, "..", "glorb", "wled16-port", "effects.json")))
        for k, p in PORT.items():
            if not isinstance(p, dict) or not p:
                continue
            for s in effect_segments(p):
                self.assertEqual(effects[str(s["fx"])], p["n"].split(" - ")[0],
                                 f"preset {k} ({p['n']}) points fx {s['fx']} at the wrong effect")


class Translation(unittest.TestCase):
    def test_fx_translation_is_one_to_one(self):
        # each fork effect must map to exactly one port effect, and no two fork effects may collide
        fwd = {}
        for k, f in FACTORY.items():
            if not isinstance(f, dict) or not f:
                continue
            for fs, ps in zip(effect_segments(f), effect_segments(PORT[k])):
                fwd.setdefault(fs["fx"], set()).add(ps["fx"])
        for fx, ports in fwd.items():
            self.assertEqual(len(ports), 1, f"fork fx {fx} maps to several port effects {sorted(ports)}")
        port_ids = [next(iter(v)) for v in fwd.values()]
        self.assertEqual(len(port_ids), len(set(port_ids)), "two fork effects map to the same port effect")

    def test_pal_translation_follows_the_palette_plan(self):
        # factory built-in ID -> the verbatim custom slot mkpalettes ships for it
        slot_for = {pid: mk.custom_id(slot) for slot, pid in mk.PLAN.items()}
        for k, f in FACTORY.items():
            if not isinstance(f, dict) or not f:
                continue
            for fs, ps in zip(effect_segments(f), effect_segments(PORT[k])):
                self.assertEqual(ps["pal"], slot_for[fs["pal"]],
                                 f"preset {k}: factory palette {fs['pal']} should map to custom "
                                 f"{slot_for[fs['pal']]}, found {ps['pal']}")


if __name__ == "__main__":
    unittest.main()
