"""The remote's number buttons call presets 1 to 7 on every lamp (WLED 16.0.1 remote.cpp).

On 2026-11-10 the couch's boot layout sat in slot 2 and button 2 switched the strip off.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*path):
    with open(os.path.join(ROOT, *path)) as stream:
        return json.load(stream)


class CouchSlots(unittest.TestCase):
    def test_every_number_button_slot_holds_a_look(self):
        presets = load("fleet", "overlays", "couch-presets.json")
        off = [slot for slot, preset in presets.items() if 1 <= int(slot) <= 7 and not preset.get("on")]
        self.assertEqual(off, [])

    def test_the_boot_preset_exists_outside_the_button_slots(self):
        boot = load("fleet", "overlays", "couch-domraem.json")["def"]["ps"]
        self.assertGreater(boot, 7)
        self.assertIn(str(boot), load("fleet", "overlays", "couch-presets.json"))


if __name__ == "__main__":
    unittest.main()
