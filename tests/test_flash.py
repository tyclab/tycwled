"""cfg_drift: which cfg changes a firmware flash may cause without counting as drift."""
import os
import sys
import tempfile
import unittest
import copy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

BASE = {"vid": 2606300, "id": {"mdns": "wled-moon"}, "um": {"AudioReactive": {"enabled": True}}}

# Every key and value kind of the /json/cfg a Gledopto GL-C-015WL served with its factory WLED 0.15.4
# (release ESP32) on 2026-11-17; names, network and identity values are neutral stand-ins.
FACTORY_0154 = {
    "rev": [1, 0], "vid": 2508020, "id": {"mdns": "wled-test", "name": "WLED", "inv": "Light", "sui": False},
    "nw": {"espnow": False, "linked_remote": "",
           "ins": [{"ssid": "test", "pskl": 12, "ip": [0, 0, 0, 0], "gw": [0, 0, 0, 0], "sn": [255, 255, 255, 0]}],
           "dns": [192, 0, 2, 1]},
    "ap": {"ssid": "WLED-AP", "pskl": 8, "chan": 1, "hide": 0, "behav": 0, "ip": [4, 3, 2, 1]},
    "wifi": {"sleep": False, "phy": False, "txpwr": 78},
    "hw": {"led": {"total": 60, "maxpwr": 850, "ledma": 0, "cct": False, "cr": False, "ic": False, "cb": 0, "fps": 42,
                   "rgbwm": 255, "ld": True, "prl": False,
                   "ins": [{"start": 0, "len": 30, "pin": [16], "order": 0, "rev": False, "skip": 0, "type": 22,
                            "ref": False, "rgbwm": 0, "freq": 0, "maxpwr": 850, "ledma": 55},
                           {"start": 30, "len": 30, "pin": [2], "order": 0, "rev": False, "skip": 0, "type": 22,
                            "ref": False, "rgbwm": 0, "freq": 0, "maxpwr": 850, "ledma": 55}]},
           "com": [],
           "btn": {"max": 4, "pull": True, "tt": 32, "mqtt": False,
                   "ins": [{"type": 2, "pin": [17], "macros": [0, 0, 0]}] + [{"type": 0, "pin": [-1], "macros": [0, 0, 0]}] * 3},
           "ir": {"pin": -1, "type": 0, "sel": True}, "relay": {"pin": 18, "rev": False, "odrain": False}, "baud": 1152,
           "if": {"i2c-pin": [-1, -1], "spi-pin": [-1, -1, -1]}},
    "light": {"scale-bri": 100, "pal-mode": 0, "aseg": False, "gc": {"bri": 1, "col": 2.8, "val": 2.8},
              "tr": {"mode": True, "fx": True, "dur": 7, "pal": False, "rpc": 5, "hrp": True},
              "nl": {"mode": 1, "dur": 60, "tbri": 0, "macro": 0}},
    "def": {"ps": 0, "on": True, "bri": 128},
    "if": {"sync": {"port0": 21324, "port1": 65506, "espnow": False,
                    "recv": {"bri": True, "col": True, "fx": True, "pal": True, "grp": 1, "seg": False, "sb": False},
                    "send": {"en": False, "dir": True, "btn": True, "va": False, "hue": False, "grp": 1, "ret": 0}},
           "nodes": {"list": True, "bcast": True},
           "live": {"en": True, "mso": False, "rlm": True, "port": 5568, "mc": False,
                    "dmx": {"uni": 1, "seqskip": False, "e131prio": 0, "addr": 1, "dss": 0, "mode": 4},
                    "timeout": 25, "maxbri": False, "no-gc": True, "offset": 0},
           "va": {"alexa": False, "macros": [0, 0], "p": 0},
           "mqtt": {"en": False, "broker": "", "port": 1883, "user": "", "pskl": 0, "cid": "WLED-test", "rtn": False,
                    "topics": {"device": "wled/test", "group": "wled/all"}},
           "hue": {"en": False, "id": 1, "iv": 25, "recv": {"on": True, "bri": True, "col": True}, "ip": [0, 0, 0, 0]},
           "ntp": {"en": False, "host": "ntp.example", "tz": 0, "offset": 0, "ampm": False, "ln": 0, "lt": 0}},
    "ol": {"clock": 0, "cntdwn": False, "min": 0, "max": 29, "o12pix": 0, "o5m": False, "osec": False, "osb": False},
    "timers": {"cntdwn": {"goal": [20, 1, 1, 0, 0, 0], "macro": 0}, "ins": []},
    "ota": {"lock": False, "lock-wifi": False, "pskl": 7, "aota": True},
    "um": {"AudioReactive": {"enabled": True, "add-palettes": False, "analogmic": {"pin": -1},
                             "digitalmic": {"type": 5, "pin": [32, 15, -1, -1]},
                             "config": {"squelch": 4, "gain": 60, "AGC": 2}, "frequency": {"scale": 3},
                             "dynamics": {"limiter": True, "rise": 80, "fall": 1400}, "sync": {"port": 11988, "mode": 0}}},
}


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

    def test_0154_source_supported(self):
        self.info.update(ver="0.15.4", release="ESP32")
        expected = wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.assertEqual(wledlab.cfg_drift(expected, self.after), [])

    def test_0154_factory_shape_migrates(self):
        info = {"ver": "0.15.4", "arch": "esp32", "release": "ESP32", "mac": "001122334455", "ip": "192.0.2.20"}
        saved = copy.deepcopy(FACTORY_0154)
        expected = wledlab.cfg_migrate_015_to_16(FACTORY_0154, info)
        self.assertEqual(FACTORY_0154, saved)
        changed = sorted(d.split(":")[0] for d in wledlab.cfg_drift(FACTORY_0154, expected))
        self.assertEqual(changed, ["hw.btn.ins", "hw.btn.max", "hw.led.ins", "hw.led.ld", "hw.led.ledma", "hw.led.prl",
                                   "if.hue.ip", "if.live.dmx.dmxInputPort", "if.live.dmx.inputEnablePin",
                                   "if.live.dmx.inputRxPin", "if.live.dmx.inputTxPin", "light.tr.fx", "light.tr.mode",
                                   "light.tr.pal", "nw.ins", "nw.linked_remote", "ota.same-subnet"])
        self.assertEqual(expected["hw"]["btn"]["ins"], [{"type": 2, "pin": [17], "macros": [0, 0, 0]}])
        self.assertEqual([(o["pin"], o["drv"], o["text"]) for o in expected["hw"]["led"]["ins"]], [([16], 0, ""), ([2], 0, "")])
        self.assertEqual((expected["nw"]["linked_remote"], expected["if"]["hue"]["ip"]), ([""], [192, 0, 2, 0]))

    def test_other_versions_and_hardware_refused(self):
        for change in ({"ver": "16.0.1"}, {"ver": "0.14.4"}, {"ver": "0.15.2"}, {"ver": "0.15.5"},
                       {"arch": "esp32s3"}, {"release": "custom"}):
            with self.subTest(change=change), \
                    self.assertRaisesRegex(ValueError, "requires a 0.15.1/0.15.3/0.15.4 classic ESP32 controller"):
                wledlab.cfg_migrate_015_to_16(self.before, self.info | change)

    def test_unreviewed_timers_and_outputs_refused(self):
        self.before["timers"]["ins"] = [{"hour": 255, "macro": 1}]
        with self.assertRaisesRegex(ValueError, "timer migration has not been reviewed"):
            wledlab.cfg_migrate_015_to_16(self.before, self.info)
        self.before["timers"]["ins"] = []
        self.before["hw"]["led"]["ins"][0]["type"] = 30
        with self.assertRaisesRegex(ValueError, "only been reviewed for WS281x RGB outputs"):
            wledlab.cfg_migrate_015_to_16(self.before, self.info)

    def test_unused_button_with_macro_refused(self):
        self.before["hw"]["btn"]["ins"][1]["macros"] = [7, 0, 0]
        with self.assertRaisesRegex(ValueError, "unassigned button contains settings"):
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

    def preflight(self, info, cfg, **changed):
        """cmd_flash offline with every argument it reads up to the upload; returns its exit message and the upload
        mock. A refusal that lets the flash go on reaches the upload, which then stops it."""
        with tempfile.TemporaryDirectory() as snap:
            args = SimpleNamespace(**{"host": "lamp", "firmware": "firmware.bin", "release": None, "mac": None,
                                      "cfg_migration": None, "skip_validation": False, "snapshot": snap, "timeout": 1,
                                      "credentials_file": None} | changed)
            with patch.object(wledlab, "get", side_effect=[info | {"vid": 2508020, "uptime": 60}, cfg, {"seg": []}]), \
                    patch.object(wledlab, "readback", return_value=b"{}"), \
                    patch.object(wledlab.subprocess, "run", side_effect=SystemExit("uploaded")) as upload, \
                    self.assertRaises(SystemExit) as stop:
                wledlab.cmd_flash(args)
        return str(stop.exception), upload

    def test_preflight_refuses_wrong_mac_before_upload(self):
        message, upload = self.preflight(self.info, self.before, mac="ff:ff:ff:ff:ff:ff")
        upload.assert_not_called()
        self.assertEqual(message, "REFUSED: controller MAC does not match --mac")

    def test_preflight_refuses_unreviewed_migration_before_upload(self):
        self.before["timers"]["ins"] = [{"hour": 255}]
        message, upload = self.preflight(self.info, self.before, cfg_migration="0.15-to-16.0.1")
        upload.assert_not_called()
        self.assertRegex(message, "^REFUSED: timer migration has not been reviewed")

    def test_preflight_refuses_unreviewed_source_version_before_upload(self):
        for ver in ("0.15.2", "0.15.5"):
            with self.subTest(ver=ver):
                message, upload = self.preflight(self.info | {"ver": ver}, self.before, cfg_migration="0.15-to-16.0.1")
                upload.assert_not_called()
                self.assertRegex(message, "^REFUSED: 0.15-to-16.0.1 migration requires a 0.15.1/0.15.3/0.15.4 classic")

    def test_preflight_reaches_the_upload_for_a_0154_source(self):
        """Control for the refusals above: the same call with a reviewed 0.15.4 source gets to the upload."""
        message, upload = self.preflight(self.info | {"ver": "0.15.4", "release": "ESP32"}, FACTORY_0154,
                                         cfg_migration="0.15-to-16.0.1")
        upload.assert_called_once()
        self.assertEqual(message, "uploaded")


if __name__ == "__main__":
    unittest.main()
