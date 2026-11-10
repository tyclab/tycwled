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
# The fleet adds power and brightness to every look. The factory presets carry neither, so a recall
# left both as they were and two lamps on the same button stayed apart (the GLORBs at 6 and 255 on
# 2026-11-10). The operator set the values that evening: 45, and 200 for the Moon.
POWER = {"on": True, "bri": 45}
# Every preset file the fleet installs: its brightness and the presets that are not looks.
FLEET = {"fleet/overlays/glorb-presets.json": (45, ()), "curtain/presets.json": (45, ()),
         "fleet/overlays/moon-presets.json": (200, ()),
         "fleet/overlays/couch-presets.json": (45, ("250",)),  # the couch's boot layout, which starts off
         # The Exoy controller's playlists carry no brightness of their own (their looks do); 30 and 31 are test patterns.
         "fleet/overlays/exoy-presets.json": (45, ("20", "21", "22", "30", "31"))}


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
                             {x: v for x, v in p.items() if x not in ("seg", *POWER)},
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


class Power(unittest.TestCase):
    def test_every_look_of_every_lamp_sets_power_and_its_brightness(self):
        for path, (brightness, layouts) in FLEET.items():
            presets = json.load(open(os.path.join(HERE, "..", path)))
            looks = {k: p for k, p in presets.items() if p and k not in layouts}
            self.assertTrue(looks, path)
            for k, p in looks.items():
                self.assertEqual((p.get("on"), p.get("bri")), (True, brightness), f"{path} preset {k} ({p.get('n')})")

    def test_no_look_changes_the_fade_time_of_a_glorb(self):
        self.assertEqual([k for k, p in PORT.items() if p and "transition" in p], [])


class Buttons(unittest.TestCase):
    """The remote's number buttons 1 to 7 recall presets 1 to 7 on every lamp at once (fleet/README.md, Remote).

    A lamp without a preset in a slot stays as it was, so the same button gave different results depending
    on what was pressed before (2026-11-10). Every lamp therefore has a look on every button, and buttons
    4 to 7, the curtain's squid looks, play the squid's arm waves on the other lamps."""

    FOLLOWERS = {"fleet/overlays/couch-presets.json": ("squid-arms-300x1.gif", 300, None),
                 "fleet/overlays/moon-presets.json": ("squid-arms-8x8.gif", 8, 8),
                 "fleet/overlays/glorb-presets.json": ("squid-arms-20x6.gif", 20, 6)}

    @staticmethod
    def load(path):
        return json.load(open(os.path.join(HERE, "..", path)))

    def test_every_lamp_has_a_look_on_every_button(self):
        for path in FLEET:
            presets = self.load(path)
            self.assertEqual([k for k in "1234567" if not presets.get(k)], [], path)

    def test_buttons_4_to_7_are_the_squid_on_every_lamp(self):
        curtain = self.load("curtain/presets.json")
        names = {k: curtain[k]["n"] for k in "4567"}
        self.assertTrue(all(name.startswith("Squid ") for name in names.values()), names)
        # The segment hatyc packages/squid.yaml sends: every field WLED reports for a segment.
        image = {"grp": 1, "spc": 0, "of": 0, "on": True, "frz": False, "bri": 255, "cct": 127, "set": 0,
                 "col": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "fx": 53, "sx": 128, "ix": 0, "pal": 0, "c1": 128, "c2": 128,
                 "c3": 16, "sel": True, "rev": False, "mi": False, "o1": False, "o2": False, "o3": False, "si": 0,
                 "m12": 0, "bm": 0}
        for path, (gif, stop, stop_y) in self.FOLLOWERS.items():
            presets = self.load(path)
            waves = {"id": 0, "start": 0, "stop": stop, "n": gif, **image}
            if stop_y:
                waves |= {"startY": 0, "stopY": stop_y, "rY": False, "mY": False, "tp": False}
            for k, name in names.items():
                self.assertEqual(presets[k]["n"], name, f"{path} preset {k}")
                self.assertEqual([s for s in presets[k]["seg"] if s.get("stop") != 0], [waves], f"{path} preset {k}")

    def test_the_couch_and_the_moon_show_their_own_look_on_buttons_1_to_3(self):
        for path in ("fleet/overlays/couch-presets.json", "fleet/overlays/moon-presets.json"):
            presets = self.load(path)
            self.assertEqual((presets["2"], presets["3"]), (presets["1"], presets["1"]), path)

    def test_the_glorbs_keep_every_port_look_with_three_moved_off_the_squid_buttons(self):
        fleet = self.load("fleet/overlays/glorb-presets.json")
        moved = {"4": "15", "5": "16", "7": "17"}
        for k, look in PORT.items():
            self.assertEqual(fleet[moved.get(k, k)], look, f"port preset {k}")
        self.assertEqual(sorted(fleet, key=int), sorted(set(PORT) - set(moved) | set(moved.values()) | set("4567"), key=int))


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
