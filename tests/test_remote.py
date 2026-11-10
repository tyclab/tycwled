"""The fleet's ESP-NOW remote map: number buttons call presets without WLED's fallback effects.

Without /remote.json WLED 16.0.1 runs presetWithFallback() for buttons 1 to 7: a lamp with no
preset in that slot shows a stock effect, and on 2026-11-10 the couch's boot layout in slot 2
switched the strip off. A JSON "ps" command leaves a lamp without that preset as it is.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import wledlab  # noqa: E402

REMOTE = os.path.join(ROOT, "fleet", "remote.json")
BUTTON_ONE = 16


def load(*path):
    with open(os.path.join(ROOT, *path)) as stream:
        return json.load(stream)


class RemoteMap(unittest.TestCase):
    def test_number_buttons_call_their_presets(self):
        buttons = load("fleet", "remote.json")
        for number in range(1, 8):
            self.assertEqual(buttons[str(BUTTON_ONE + number - 1)]["cmd"], {"ps": number})

    def test_no_button_brings_a_fallback_effect(self):
        commands = [entry["cmd"] for entry in load("fleet", "remote.json").values() if isinstance(entry, dict)]
        self.assertEqual([c for c in commands if not isinstance(c, dict)], [])


class CouchSlots(unittest.TestCase):
    def test_every_number_button_slot_holds_a_look(self):
        presets = load("fleet", "overlays", "couch-presets.json")
        off = [slot for slot, preset in presets.items() if 1 <= int(slot) <= 7 and not preset.get("on")]
        self.assertEqual(off, [])

    def test_the_boot_preset_exists_outside_the_button_slots(self):
        boot = load("fleet", "overlays", "couch-domraem.json")["def"]["ps"]
        self.assertGreater(boot, 7)
        self.assertIn(str(boot), load("fleet", "overlays", "couch-presets.json"))


class InstallRemote(unittest.TestCase):
    ARGS = dict(host="lamp", ledmap=None, palette=None, presets=None, cfg=None, reboot=False, effects=None)
    LAMP = [{"ver": "16.0.1", "leds": {}}, {}]

    def test_uploads_the_map_and_reads_it_back(self):
        raw = open(REMOTE, "rb").read()
        with patch.object(wledlab, "upload", return_value="ok") as upload, \
                patch.object(wledlab, "readback", return_value=raw), \
                patch.object(wledlab, "get", side_effect=self.LAMP):
            wledlab._cmd_install(SimpleNamespace(**self.ARGS, remote=REMOTE))
        upload.assert_called_once_with("lamp", "/remote.json", REMOTE)

    def test_stops_when_the_map_did_not_land(self):
        with patch.object(wledlab, "upload", return_value="ok"), \
                patch.object(wledlab, "readback", return_value=b""), \
                patch.object(wledlab, "get", side_effect=self.LAMP), self.assertRaises(SystemExit):
            wledlab._cmd_install(SimpleNamespace(**self.ARGS, remote=REMOTE))


if __name__ == "__main__":
    unittest.main()
