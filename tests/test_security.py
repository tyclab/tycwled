"""WLED 16 security form behavior, including its global PIN unlock and OTA lock."""
import copy
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402


class Lamp:
    def __init__(self):
        self.pin, self.password, self.unlocked = "", "old-password", True
        self.cfg = {"nw": {"linked_remote": ["aabbccddeeff"]}, "light": {"gc": {"col": 1}},
                    "ota": {"lock": False, "lock-wifi": False, "pskl": 12, "aota": True, "same-subnet": False}}
        self.requests = []

    def request(self, host, path, fields=None):
        self.requests.append((path, fields))
        if path == "/settings/lock":
            self.unlocked = not self.pin
            return 200
        if path == "/update":
            return 401 if self.cfg["ota"]["lock"] or not self.unlocked else 200
        if path != "/settings/sec":
            raise AssertionError(path)
        if fields is None:
            return 200 if self.unlocked else 401
        if not self.unlocked:
            self.unlocked = fields.get("PIN") == self.pin
            return 200 if self.unlocked else 401
        if "PIN" in fields:
            self.pin = fields["PIN"]
        if not self.cfg["ota"]["lock"] or fields.get("OP") == self.password:
            if not self.cfg["ota"]["lock"]:
                self.password = fields["OP"]
                self.cfg["ota"]["pskl"] = len(self.password)
            for key, field in (("lock", "NO"), ("lock-wifi", "OW"), ("aota", "AO"), ("same-subnet", "SU")):
                self.cfg["ota"][key] = field in fields
        return 200

    def get(self, host, path):
        if path == "/json/info":
            return {"ver": "16.0.1", "mac": "aabbccddeeff"}
        if path == "/json/cfg":
            return copy.deepcopy(self.cfg)
        if path == "/json/state":
            return {"on": True, "bri": 100}
        raise AssertionError(path)


class Security(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = os.path.join(self.directory.name, "credentials.json")
        with open(self.file, "w") as stream:
            json.dump({"pin": "4872", "ota_password": "example-private-password-32chars"}, stream)
        self.args = SimpleNamespace(host="lamp", mac="aa:bb:cc:dd:ee:ff", credentials_file=self.file)
        self.lamp = Lamp()
        for name, replacement in (("settings_request", self.lamp.request), ("get", self.lamp.get),
                                  ("readback", lambda *_: b'{"1":{"n":"preserved"}}')):
            mocked = patch.object(wledlab, name, side_effect=replacement)
            mocked.start()
            self.addCleanup(mocked.stop)
        sleep = patch.object(wledlab.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def test_security_preserves_remotes_light_presets_and_network_flags(self):
        before = copy.deepcopy(self.lamp.cfg)
        wledlab.cmd_secure(self.args)
        self.assertEqual(self.lamp.pin, "4872")
        self.assertFalse(self.lamp.unlocked)
        self.assertEqual(self.lamp.cfg["nw"], before["nw"])
        self.assertEqual(self.lamp.cfg["light"], before["light"])
        self.assertEqual(self.lamp.cfg["ota"], before["ota"] | {
            "lock": True, "lock-wifi": True, "pskl": len(self.lamp.password)})
        self.assertFalse(any(fields and "RS" in fields for _, fields in self.lamp.requests))
        wledlab.cmd_secure(self.args)
        self.assertFalse(self.lamp.unlocked)
        self.assertTrue(self.lamp.cfg["ota"]["lock"])

    def test_unknown_existing_pin_refused_without_changing_settings(self):
        self.lamp.pin = "1111"
        before = copy.deepcopy(self.lamp.cfg)
        with self.assertRaisesRegex(RuntimeError, "PIN was rejected"):
            wledlab.cmd_secure(self.args)
        self.assertEqual(before, self.lamp.cfg)
        self.assertEqual(self.lamp.pin, "1111")
        self.assertFalse(self.lamp.unlocked)

    def test_wrong_controller_refused_before_any_security_request(self):
        self.args.mac = "000000000000"
        with self.assertRaisesRegex(RuntimeError, "specified MAC"):
            wledlab.cmd_secure(self.args)
        self.assertEqual(self.lamp.requests, [])

    def test_ota_failure_restores_lock_and_relocks_pin(self):
        wledlab.cmd_secure(self.args)
        before = copy.deepcopy(self.lamp.cfg)
        with self.assertRaisesRegex(RuntimeError, "upload failed"):
            with wledlab.settings_access("lamp", self.file) as access:
                access.unlock_ota(before["ota"])
                self.assertFalse(self.lamp.cfg["ota"]["lock"])
                raise RuntimeError("upload failed")
        self.assertEqual(before, self.lamp.cfg)
        self.assertFalse(self.lamp.unlocked)

    def test_ota_restore_authenticates_after_reboot_before_drift_read(self):
        wledlab.cmd_secure(self.args)
        before = copy.deepcopy(self.lamp.cfg)
        with wledlab.settings_access("lamp", self.file) as access:
            access.unlock_ota(before["ota"])
            self.lamp.unlocked = False
            access.restore_ota()
            self.assertEqual(before, self.lamp.cfg)
        self.assertFalse(self.lamp.unlocked)

    def test_wrong_ota_password_never_opens_update(self):
        self.lamp.pin, self.lamp.unlocked = "4872", False
        self.lamp.cfg["ota"]["lock"] = True
        with self.assertRaisesRegex(RuntimeError, "OTA credential"):
            with wledlab.settings_access("lamp", self.file) as access:
                access.unlock_ota(self.lamp.cfg["ota"])
        self.assertTrue(self.lamp.cfg["ota"]["lock"])
        self.assertFalse(self.lamp.unlocked)

    def test_install_relocks_after_failure(self):
        wledlab.cmd_secure(self.args)
        with patch.object(wledlab, "_cmd_install", side_effect=SystemExit("bad config")), self.assertRaises(SystemExit):
            wledlab.cmd_install(self.args)
        self.assertFalse(self.lamp.unlocked)
        self.assertTrue(self.lamp.cfg["ota"]["lock"])


if __name__ == "__main__":
    unittest.main()
