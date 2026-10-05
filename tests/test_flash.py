"""cfg_drift: which cfg changes a firmware flash may cause without counting as drift."""
import os
import sys
import unittest
import copy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

BASE = {"vid": 2606300, "id": {"mdns": "wled-moon"}, "um": {"AudioReactive": {"enabled": True}}}


class CfgDrift(unittest.TestCase):
    def test_build_stamp_and_new_usermod_pass(self):
        after = {"vid": 2609300, "id": {"mdns": "wled-moon"},
                 "um": {"AudioReactive": {"enabled": True}, "Syslog": {"enabled": True, "port": 1515}}}
        self.assertEqual(wledlab.cfg_drift(BASE, after), [])

    def test_changed_setting_is_drift(self):
        after = {"vid": 2606300, "id": {"mdns": "wled-other"}, "um": {"AudioReactive": {"enabled": True}}}
        self.assertEqual(wledlab.cfg_drift(BASE, after), ['id.mdns: "wled-moon" -> "wled-other"'])

    def test_existing_usermod_change_is_drift(self):
        after = {"vid": 2606300, "id": {"mdns": "wled-moon"}, "um": {"AudioReactive": {"enabled": False}}}
        self.assertEqual(wledlab.cfg_drift(BASE, after), ["um.AudioReactive.enabled: true -> false"])

    def test_lost_key_is_drift(self):
        after = {"vid": 2606300, "id": {"mdns": "wled-moon"}, "um": {}}
        self.assertEqual(wledlab.cfg_drift(BASE, after), ['um.AudioReactive: {"enabled": true} -> <absent>'])


class SpareMigration(unittest.TestCase):
    def setUp(self):
        self.info = {"ver": "0.15.3", "arch": "esp32", "release": "ESP32_Ethernet", "mac": "001122334455", "ip": "192.0.2.20"}
        self.before = {
            "vid": 2508020,
            "nw": {"espnow": True, "linked_remote": "aabbccddeeff", "ins": [{"ssid": "test", "pskl": 12}]},
            "hw": {"led": {"ledma": 0, "ld": True, "prl": True, "fps": 42,
                           "ins": [{"type": 22, "pin": [16], "len": 30}]},
                   "btn": {"max": 4, "ins": [{"type": 2, "pin": [17], "macros": [1, 2, 3]},
                                   {"type": 0, "pin": [-1], "macros": [0, 0, 0]}]},
                   "relay": {"pin": 18, "rev": False}},
            "light": {"tr": {"mode": True, "fx": True, "pal": False, "dur": 7},
                      "gc": {"col": 2.8, "bri": 1, "val": 2.8}},
            "timers": {"ins": []}, "ota": {"lock": False},
            "if": {"live": {"dmx": {"mode": 4}}, "hue": {"ip": [0, 0, 0, 0], "en": False}},
            "um": {"AudioReactive": {"digitalmic": {"type": 5, "pin": [32, 15, -1, -1]}}},
        }
        self.after = {
            "vid": 2610050,
            "nw": {"espnow": True, "linked_remote": ["aabbccddeeff"],
                   "ins": [{"ssid": "test", "pskl": 12, "bssid": ""}]},
            "hw": {"led": {"fps": 42, "ins": [{"type": 22, "pin": [16], "len": 30, "drv": 0, "text": ""}]},
                   "btn": {"max": 32, "ins": [{"type": 2, "pin": [17], "macros": [1, 2, 3]}]},
                   "relay": {"pin": 18, "rev": False}},
            "light": {"tr": {"dur": 7}, "gc": {"col": 2.8, "bri": 1, "val": 2.8}},
            "timers": {"ins": []}, "ota": {"lock": False, "same-subnet": True},
            "if": {"live": {"dmx": {"mode": 4, "inputRxPin": -1, "inputTxPin": -1,
                                      "inputEnablePin": -1, "dmxInputPort": 2}},
                   "hue": {"ip": [192, 0, 2, 0], "en": False}},
            "um": {"AudioReactive": {"digitalmic": {"type": 5, "pin": [32, 15, -1, -1]}},
                   "Syslog": {"enabled": True}},
        }

    def test_reviewed_migration_preserves_hardware_and_remote(self):
        saved = copy.deepcopy(self.before)
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.assertEqual(wledlab.cfg_drift(expected, self.after), [])
        self.assertEqual(self.before, saved)
        self.assertTrue(wledlab.cfg_drift(self.before, self.after))  # opt-in only

    def test_missing_or_changed_settings_are_still_drift(self):
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        changes = [("nw", "ins", []), ("nw", "linked_remote", []), ("hw", "relay", {}),
                   ("light", "gc", {}), ("um", "AudioReactive", {})]
        for section, key, value in changes:
            with self.subTest(path=f"{section}.{key}"):
                after = copy.deepcopy(self.after)
                after[section][key] = value
                self.assertTrue(wledlab.cfg_drift(expected, after))

    def test_wrong_driver_or_lost_output_is_drift(self):
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        for key, value in (("drv", 1), ("pin", [2]), ("len", 0)):
            after = copy.deepcopy(self.after)
            after["hw"]["led"]["ins"][0][key] = value
            self.assertTrue(wledlab.cfg_drift(expected, after))

    def test_both_spare_versions_supported(self):
        self.info.update(ver="0.15.1", release="ESP32")
        self.before["nw"]["linked_remote"] = ""
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.assertEqual(expected["nw"]["linked_remote"], [""])

    def test_other_versions_and_hardware_refused(self):
        for change in ({"ver": "16.0.1"}, {"ver": "0.14.4"}, {"arch": "esp32s3"}, {"release": "custom"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                wledlab.cfg_migrate_015_to_16(self.before, self.info | change)

    def test_unreviewed_timers_and_outputs_refused(self):
        self.before["timers"]["ins"] = [{"hour": 255, "macro": 1}]
        with self.assertRaises(ValueError):
            wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.before["timers"]["ins"] = []
        self.before["hw"]["led"]["ins"][0]["type"] = 30
        with self.assertRaises(ValueError):
            wledlab.cfg_migrate_015_to_16(self.before, self.info)

    def test_unused_button_with_macro_refused(self):
        self.before["hw"]["btn"]["ins"][1]["macros"] = [7, 0, 0]
        with self.assertRaises(ValueError):
            wledlab.cfg_migrate_015_to_16(self.before, self.info)

    def test_configured_hue_and_network_settings_preserved(self):
        self.before["if"]["hue"]["ip"] = [192, 0, 2, 40]
        self.before["nw"]["ins"][0]["ip"] = [192, 0, 2, 20]
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.assertEqual(expected["if"]["hue"]["ip"], [192, 0, 2, 40])
        self.assertEqual(expected["nw"]["ins"][0]["ip"], [192, 0, 2, 20])

    def test_unexpected_dmx_pin_and_ota_access_change_are_drift(self):
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        after = copy.deepcopy(self.after)
        after["if"]["live"]["dmx"]["inputRxPin"] = 16
        after["ota"]["same-subnet"] = False
        drift = wledlab.cfg_drift(expected, after)
        self.assertEqual(len(drift), 2)

    def test_preflight_refuses_wrong_mac_before_upload(self):
        args = SimpleNamespace(host="lamp", mac="ff:ff:ff:ff:ff:ff", cfg_migration=None)
        with patch.object(wledlab, "get", side_effect=[self.info, self.before]), \
                patch.object(wledlab, "readback", return_value=b"{}"), \
                patch.object(wledlab.subprocess, "run") as upload, self.assertRaises(SystemExit):
            wledlab.cmd_flash(args)
        upload.assert_not_called()

    def test_preflight_refuses_unreviewed_migration_before_upload(self):
        args = SimpleNamespace(host="lamp", mac=None, cfg_migration="0.15-to-16.0.1")
        self.before["timers"]["ins"] = [{"hour": 255}]
        with patch.object(wledlab, "get", side_effect=[self.info, self.before]), \
                patch.object(wledlab, "readback", return_value=b"{}"), \
                patch.object(wledlab.subprocess, "run") as upload, self.assertRaises(SystemExit):
            wledlab.cmd_flash(args)
        upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
