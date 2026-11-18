"""cfg_drift: which cfg changes a firmware flash may cause without counting as drift."""
import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import copy
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

BASE = {"vid": 2606300, "id": {"mdns": "wled-moon"}, "um": {"AudioReactive": {"enabled": True}}}


def djb2(text):
    value = 5381
    for c in text.encode():
        value = (value * 33 + c) & 0xFFFFFFFF
    return value


def image(release="ESP32", at=288, hash_ok=True, version=1):
    """The head of a WLED 16.0.1 image as the firmware lays it out (wled_metadata.h wled_metadata_t, packed: magic
    "WSTS" little-endian, desc_version, wled_version[48], release_name[48], hash, safe_update_version[3]); an ESP32
    image holds it at byte 288, after the image header, the segment header and Espressif's 256-byte description."""
    desc = b"STSW" + version.to_bytes(4, "little") + b"16.0.1".ljust(48, b"\0") + release.encode().ljust(48, b"\0") \
        + (djb2(release) ^ (0 if hash_ok else 1)).to_bytes(4, "little") + bytes([0, 15, 3])
    return b"\xe9" + bytes(at - 1) + desc + bytes(64)


# The lamp's answer to a refused upload (wled_server.cpp serveMessage: PAGE_msg with head, "</h2>", text and the Back
# button), as TycDodecaRechts gave it on 2026-11-18: WLED 16.0.1 quotes the uploaded name with the stack bytes after it.
REFUSED_PAGE = (b'<!DOCTYPE html> <html lang=en> <head> <meta content="width=device-width" name=viewport> <title>WLED Message'
                b'</title> <script> function B(){window.history.back()} </script> <style> @import url("style.css"); </style>'
                b" </head> <body> <h2>Update failed!</h2>Firmware release name mismatch: current='ESP32', uploaded='ESP32"
                b"\xe9\x10'. Enable 'Ignore firmware validation' to proceed anyway.<br><br><button type=\"button\" "
                b'class="bt" onclick="B()">Back</button></body> </html>')
DENIED_PAGE = (b"<html><body> <h2>Access Denied</h2>Please unlock OTA in security settings!<br><br><button>Back</button>"
               b"</body> </html>")

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
            firmware = os.path.join(snap, "firmware.bin")
            with open(firmware, "wb") as f:
                f.write(changed.pop("image", image(info["release"])))
            args = SimpleNamespace(**{"host": "lamp", "firmware": firmware, "release": None, "mac": None,
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

    def test_preflight_refuses_an_image_of_another_release_before_upload(self):
        message, upload = self.preflight(self.info | {"release": "ESP32"}, self.before, image=image("ESP32_Ethernet"))
        upload.assert_not_called()
        self.assertEqual(message, "REFUSED: the image is release 'ESP32_Ethernet', the lamp runs 'ESP32'; nothing was "
                                  "written (--skip-validation when the release changes on purpose)")

    def test_preflight_refuses_an_image_without_a_release_name_before_upload(self):
        for name, data in (("no structure", bytes(8192)), ("wrong hash", image("ESP32", hash_ok=False))):
            with self.subTest(name):
                message, upload = self.preflight(self.info | {"release": "ESP32"}, self.before, image=data)
                upload.assert_not_called()
                self.assertEqual(message, "REFUSED: firmware.bin declares no WLED release name; nothing was written")

    def test_preflight_refuses_an_image_with_a_newer_description_before_upload(self):
        """The lamp is told to skip its whole check, and from description version 2 on that check is more than the
        release name."""
        newer = image("ESP32", version=2)
        message, upload = self.preflight(self.info | {"release": "ESP32"}, self.before, image=newer)
        upload.assert_not_called()
        self.assertEqual(message, "REFUSED: the image's description has version 2, and this tool knows the check of "
                                  "version 1 only; nothing was written (--skip-validation flashes it unchecked)")
        message, upload = self.preflight(self.info | {"release": "ESP32"}, self.before, image=newer, skip_validation=True)
        upload.assert_called_once()
        self.assertEqual(message, "uploaded")

    def test_a_missing_firmware_file_is_refused_before_the_lamp_is_asked(self):
        """Also with --skip-validation, where no check opens the file: curl would fail and the tool restart the lamp."""
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(host="lamp", firmware=os.path.join(folder, "firmware.bin"), skip_validation=True,
                                   credentials_file="credentials.json")
            with patch.object(wledlab, "get") as get, patch.object(wledlab, "settings_access") as access, \
                    patch.object(wledlab.subprocess, "run") as upload, self.assertRaises(SystemExit) as stop:
                wledlab.cmd_flash(args)
        for mock in (get, access, upload):
            mock.assert_not_called()
        self.assertEqual(str(stop.exception), f"REFUSED: no firmware file at {args.firmware}; the lamp was not asked anything")

    def test_skip_validation_lets_another_release_reach_the_upload(self):
        message, upload = self.preflight(self.info | {"release": "ESP32"}, self.before, image=image("ESP32_Ethernet"),
                                         skip_validation=True)
        upload.assert_called_once()
        self.assertEqual(message, "uploaded")

    def test_the_upload_tells_the_lamp_to_skip_its_own_release_check(self):
        """The check is release_refusal's; the lamp's own refuses equal names on some builds and resets its segments."""
        _, upload = self.preflight(self.info | {"release": "ESP32"}, self.before)
        command = upload.call_args.args[0]
        self.assertEqual(command[:4], ["curl", "-s", "-m", "300"])
        self.assertEqual(command[-1], "http://lamp/update")
        fields = [command[i + 1] for i in range(len(command) - 1) if command[i] == "-F"]
        self.assertEqual(fields[0], "skipValidation=1")
        self.assertRegex(fields[1], r"^update=@.*firmware\.bin$")
        self.assertEqual(len(fields), 2)


class ImageRelease(unittest.TestCase):
    def write(self, data):
        handle, path = tempfile.mkstemp(suffix=".bin")
        self.addCleanup(os.remove, path)
        with os.fdopen(handle, "wb") as f:
            f.write(data)
        return path

    def test_reads_the_name_where_the_firmware_finds_it(self):
        self.assertEqual(wledlab.image_release(self.write(image("ESP32"))), ("ESP32", 1))
        self.assertEqual(wledlab.image_release(self.write(image("ESP32-S3_8MB_qspi"))), ("ESP32-S3_8MB_qspi", 1))
        self.assertEqual(wledlab.image_release(self.write(image("ESP8266", at=4096))), ("ESP8266", 1))
        self.assertEqual(wledlab.image_release(self.write(image("ESP32", version=2))), ("ESP32", 2))

    def test_the_hash_is_the_one_a_real_image_carries(self):
        # exoy_domraem.bin 393bc20d... (vid 2611181): description version 1 in bytes 292..295, its release name "ESP32"
        # at 344, the hash in 392..395, the version an update may come from (0.15.3) in 396..398.
        data = image("ESP32")
        self.assertEqual(data[292:296], b"\x01\0\0\0")
        self.assertEqual(data[344:349], b"ESP32")
        self.assertEqual(int.from_bytes(data[392:396], "little"), 0x0D0E7972)
        self.assertEqual(data[396:399], bytes([0, 15, 3]))

    def test_a_structure_with_a_wrong_hash_is_passed_over(self):
        self.assertIsNone(wledlab.image_release(self.write(image("ESP32", hash_ok=False))))
        both = image("ESP32", hash_ok=False) + image("ESP32_Ethernet")[1:]
        self.assertEqual(wledlab.image_release(self.write(both)), ("ESP32_Ethernet", 1))

    def test_no_name_in_an_image_without_the_structure_or_with_an_empty_name(self):
        self.assertIsNone(wledlab.image_release(self.write(bytes(8192))))
        self.assertIsNone(wledlab.image_release(self.write(image(""))))
        self.assertIsNone(wledlab.image_release(self.write(b"\xe9" + bytes(287) + b"STSW" + bytes(20))))

    def test_the_rule_is_the_firmwares(self):
        path = self.write(image("ESP32"))
        self.assertIsNone(wledlab.release_refusal(path, "ESP32"))
        self.assertIsNone(wledlab.release_refusal(path, "ESP32_V4"))
        self.assertIsNone(wledlab.release_refusal(self.write(image("ESP32_V4")), "ESP32"))
        self.assertIn("the image is release 'ESP32', the lamp runs 'ESP32_Ethernet'", wledlab.release_refusal(path, "ESP32_Ethernet"))
        self.assertIn("the lamp runs None", wledlab.release_refusal(path, None))
        self.assertIn("description has version 2", wledlab.release_refusal(self.write(image("ESP32", version=2)), "ESP32"))


class FailedUpload(unittest.TestCase):
    """An upload that ends without the new firmware: what the tool says and how it leaves the lamp."""

    INFO = {"ver": "16.0.1", "vid": 2611180, "release": "ESP32", "mac": "001122334455", "uptime": 5000}
    STATE = {"on": False, "bri": 129, "ps": -1, "pl": -1, "mainseg": 0, "seg": [{"id": 0, "fx": 251, "sx": 0}]}
    REFUSAL = ("OTA refused or failed (curl 0): Update failed! Firmware release name mismatch: current='ESP32', "
               "uploaded='ESP32??'. Enable 'Ignore firmware validation' to proceed anyway. Back\n")
    RESTART = ("lamp", "/json/state", {"rb": True})
    LOOK = ("lamp", "/json/state", wledlab.look_request(STATE))

    def flash(self, page, info_after, restarted=None, run=None, info=None):
        """cmd_flash with the lamp answering the upload with `page` and the undo's /json/info with `info_after` (an
        exception is raised). The clock stands at 1000 and moves in the tool's sleeps and by two seconds in every
        state post (a post that had to be tried again). Returns the exit message,
        stderr at the end (`said`) and as it was when the undo asked the lamp (`said_at_undo`), the state posts and
        the wait_for_restart mock."""
        answers, clock, said, at_undo = [info or self.INFO, {"ota": {}}, self.STATE, info_after], [1000.0], io.StringIO(), []

        def get(*args, **kwargs):
            if len(answers) == 1:
                at_undo.append(said.getvalue())
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        def sleep(seconds):
            clock[0] += seconds
        with tempfile.TemporaryDirectory() as snap:
            firmware = os.path.join(snap, "firmware.bin")
            with open(firmware, "wb") as f:
                f.write(image("ESP32"))
            args = SimpleNamespace(host="lamp", firmware=firmware, release="ESP32", mac=None, cfg_migration=None,
                                   skip_validation=False, snapshot=snap, timeout=1, credentials_file=None)
            answer = SimpleNamespace(returncode=0, stdout=page.decode("utf-8", "replace"), stderr="")
            with patch.object(wledlab, "get", side_effect=get), \
                    patch.object(wledlab, "readback", return_value=b"{}"), \
                    patch.object(wledlab, "post", side_effect=lambda *args: sleep(2)) as post, \
                    patch.object(wledlab.time, "sleep", side_effect=sleep), \
                    patch.object(wledlab.time, "time", side_effect=lambda: clock[0]), \
                    patch.object(wledlab, "wait_for_restart", return_value=restarted) as wait, \
                    patch.object(wledlab.subprocess, "run", **({"side_effect": run} if run else {"return_value": answer})), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(said), \
                    self.assertRaises(SystemExit) as stop:
                wledlab.cmd_flash(args)
        return SimpleNamespace(message=str(stop.exception), said=said.getvalue(), said_at_undo="".join(at_undo),
                               posts=[call.args for call in post.call_args_list], wait=wait)

    def test_a_refusal_after_the_upload_began_restarts_the_lamp_and_puts_its_look_back(self):
        result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 5004}, restarted={"uptime": 9, "vid": 2611180})
        self.assertEqual(result.posts, [self.RESTART, self.LOOK])
        # the restart is asked three seconds after the lamp's answer, and awaited from the moment before it was asked
        # (the post takes two seconds here), for --timeout
        result.wait.assert_called_once_with("lamp", 1003.0, 1)
        self.assertEqual(result.said, self.REFUSAL)
        self.assertEqual(result.message, "The lamp was restarted to undo the segment reset of the upload, runs vid 2611180 "
                                         "and got its look back")

    def test_the_lamps_answer_is_out_before_the_undo_asks_the_lamp_anything(self):
        result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 5004}, restarted={"uptime": 9, "vid": 2611180})
        self.assertEqual(result.said_at_undo, self.REFUSAL)

    def test_whatever_the_undo_meets_the_lamps_answer_and_a_sentence_about_the_lamp_remain(self):
        """An answer cut short is no URLError (http.client.IncompleteRead, BadStatusLine); neither is an OSError from
        reading the answer. The tool once ended in a traceback there and the lamp's answer was lost. The sentence
        stays one line, also when the error quotes a line of the lamp's with its line end."""
        for error in (http.client.IncompleteRead(b"{"), http.client.BadStatusLine("garbage\r\n"), OSError("reset"),
                      urllib.error.URLError("refused"), KeyError("uptime"), RuntimeError("anything")):
            with self.subTest(type(error).__name__):
                result = self.flash(REFUSED_PAGE, error)
                self.assertEqual(result.said, self.REFUSAL)
                self.assertRegex(result.message, rf"^The lamp could not be put back as it was \({type(error).__name__}: .*\): "
                                                 "check it$")
                self.assertEqual(result.posts, [])

    def test_a_lamp_that_does_not_come_back_from_that_restart_is_named(self):
        result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 5004}, restarted=None)
        self.assertEqual(result.posts, [self.RESTART])
        self.assertEqual(result.message, "The lamp did not come back from the restart that undoes the upload's segment "
                                         "reset: check it")

    def test_a_lamp_that_restarted_by_itself_only_gets_its_look_back(self):
        """Read from the uptime alone: into the new firmware, or back into the old one after a crash (same vid)."""
        for vid in (2611181, 2611180):
            with self.subTest(vid=vid):
                result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 4, "vid": vid})
                self.assertEqual(result.posts, [self.LOOK])
                result.wait.assert_not_called()
                self.assertEqual(result.message, f"The lamp restarted by itself, runs vid {vid} and got its look back")

    def test_a_lamp_flashed_right_after_its_boot_is_restarted_when_its_uptime_went_on(self):
        result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 9}, restarted={"uptime": 5, "vid": 2611180},
                            info=self.INFO | {"uptime": 6})
        self.assertEqual(result.posts, [self.RESTART, self.LOOK])

    def test_a_refusal_for_access_leaves_the_lamp_alone(self):
        result = self.flash(DENIED_PAGE, self.INFO)
        self.assertEqual(result.posts, [])
        result.wait.assert_not_called()
        self.assertEqual(result.said, "OTA refused or failed (curl 0): Access Denied Please unlock OTA in security settings! "
                                      "Back\n")
        self.assertEqual(result.message, "The lamp refused access before the upload began and is as it was")

    def test_an_answer_with_bytes_that_are_no_text_is_read(self):
        """The lamp's page through a real process, decoded as cmd_flash asks for it: TycDodecaRechts's refusal held
        0xe9 after the name, and the tool ended in a UnicodeDecodeError instead of the lamp's words."""
        real_run = wledlab.subprocess.run

        def run(command, **kwargs):
            return real_run([sys.executable, "-c", f"import sys; sys.stdout.buffer.write({REFUSED_PAGE!r})"], **kwargs)
        result = self.flash(REFUSED_PAGE, self.INFO | {"uptime": 5004}, restarted={"uptime": 9, "vid": 2611180}, run=run)
        self.assertEqual(result.said, self.REFUSAL)


class WaitForRestart(unittest.TestCase):
    """The wait itself: a lamp has restarted once its uptime is shorter than the time since the restart was asked."""

    def wait(self, answers, timeout):
        """wait_for_restart, asked at clock 1000, with /json/info answering in turn (an exception is raised, bytes are
        the body, a dict is served as JSON; the last answer repeats). The clock moves in the tool's sleeps only.
        Returns the result and the clock at the end."""
        clock = [1000.0]

        def urlopen(url, timeout=None):
            self.assertEqual(url, "http://lamp/json/info")
            answer = answers.pop(0) if len(answers) > 1 else answers[0]
            if isinstance(answer, Exception):
                raise answer
            return io.BytesIO(answer if isinstance(answer, bytes) else json.dumps(answer).encode())

        def sleep(seconds):
            clock[0] += seconds
        with patch.object(wledlab.urllib.request, "urlopen", side_effect=urlopen), \
                patch.object(wledlab.time, "sleep", side_effect=sleep), \
                patch.object(wledlab.time, "time", side_effect=lambda: clock[0]):
            return wledlab.wait_for_restart("lamp", 1000.0, timeout), clock[0]

    def test_it_waits_through_every_answer_that_is_no_restart(self):
        info, clock = self.wait([
            {"uptime": 8},                         # 1000: booted eight seconds before the restart was asked
            urllib.error.URLError("refused"),      # 1003: down
            http.client.IncompleteRead(b"{"),      # 1006: an answer cut short
            b"<html>",                             # 1009: no JSON
            {"ver": "16.0.1"},                     # 1012: no uptime
            {"uptime": 5015},                      # 1015: still the old run
            {"uptime": 12, "vid": 2611180},        # 1018: started twelve seconds ago, after the restart was asked
        ], timeout=60)
        self.assertEqual(info, {"uptime": 12, "vid": 2611180})
        self.assertEqual(clock, 1018.0)

    def test_a_lamp_that_never_restarts_gives_none_once_the_time_is_up(self):
        info, clock = self.wait([{"uptime": 5000}], timeout=10)
        self.assertIsNone(info)
        self.assertEqual(clock, 1012.0)


class Retry(unittest.TestCase):
    def test_a_lost_request_is_tried_again_also_when_its_answer_was_cut_short(self):
        for error in (http.client.IncompleteRead(b"{"), http.client.BadStatusLine("\x00"), urllib.error.URLError("refused"),
                      TimeoutError(), ConnectionResetError(), OSError("reset")):
            with self.subTest(type(error).__name__):
                answers = [error, "answer"]

                def request():
                    answer = answers.pop(0)
                    if isinstance(answer, Exception):
                        raise answer
                    return answer
                with patch.object(wledlab.time, "sleep"):
                    self.assertEqual(wledlab._retry(request), "answer")

    def test_an_answer_that_is_wrong_is_not_asked_for_again(self):
        calls = []

        def request():
            calls.append(1)
            raise ValueError("no JSON")
        with patch.object(wledlab.time, "sleep"), self.assertRaises(ValueError):
            wledlab._retry(request)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
