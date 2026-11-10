"""`remotes` reports the paired ESP-NOW remotes and the last sender a lamp heard, and replaces the list.

WLED 16.0.1 records every sender before it drops an unlinked one (udp.cpp), and shows it only on the
PIN-locked Wi-Fi settings page; a /json/cfg write replaces the whole list (cfg.cpp)."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

LINKED = ["704bcac8d198", "704bcaca4b78"]


class Lamp:
    def __init__(self, heard="704bcaca4b78"):
        self.pin, self.unlocked, self.heard = "4872", False, heard
        self.cfg = {"nw": {"espnow": True, "linked_remote": list(LINKED)}, "light": {"gc": {"col": 1}},
                    "ota": {"lock": True, "lock-wifi": True}}
        self.posts, self.side_effect = [], None

    def request(self, host, path, fields=None):
        if path == "/settings/lock":
            self.unlocked = False
            return 200
        if path != "/settings/sec":
            raise AssertionError(path)
        if fields is None:
            return 200 if self.unlocked else 401
        self.unlocked = fields.get("PIN") == self.pin
        return 200 if self.unlocked else 401

    def get(self, host, path):
        if path == "/json/info":
            return {"ver": "16.0.1", "mac": "f0f5bd569528"}
        if path == "/json/cfg":
            return copy.deepcopy(self.cfg)
        raise AssertionError(path)

    def text(self, host, path):
        if not self.unlocked:
            raise urllib.error.HTTPError(path, 401, "PIN required", {}, None)
        assert path == "/settings/s.js?p=1"
        remotes = "".join(f'aR("RM{i}","{mac}");' for i, mac in enumerate(self.cfg["nw"]["linked_remote"]))
        heard = f'd.getElementsByClassName("rlid")[0].innerHTML="{self.heard}";' if self.heard else ""
        return f'function GetV(){{var d=document;rstR();{remotes}tE();{heard}}}'

    def post(self, host, path, body):
        assert self.unlocked and path == "/json/cfg"
        self.posts.append(body)
        self.cfg["nw"]["linked_remote"] = list(body["nw"]["linked_remote"])
        if "espnow" in body["nw"]:
            self.cfg["nw"]["espnow"] = body["nw"]["espnow"]
        if self.side_effect:
            self.side_effect(self.cfg)
        return b'{"success":true}'


class Remotes(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.file = os.path.join(directory.name, "credentials.json")
        with open(self.file, "w") as stream:
            json.dump({"pin": "4872", "ota_password": "example-private-password-32chars"}, stream)
        self.lamp = Lamp()
        for name, replacement in (("settings_request", self.lamp.request), ("get", self.lamp.get),
                                  ("settings_text", self.lamp.text), ("post", self.lamp.post)):
            mocked = patch.object(wledlab, name, side_effect=replacement)
            mocked.start()
            self.addCleanup(mocked.stop)
        sleep = patch.object(wledlab.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def run_remotes(self, link=None, mac="f0:f5:bd:56:95:28"):
        out = io.StringIO()
        with redirect_stdout(out):
            wledlab.cmd_remotes(SimpleNamespace(host="lamp", mac=mac, credentials_file=self.file, link=link))
        return json.loads(out.getvalue())

    def test_report_reads_the_last_sender_behind_the_pin_and_relocks(self):
        report = self.run_remotes()
        self.assertEqual(report, {"host": "lamp", "espnow": True, "linked": LINKED, "last_heard": "704bcaca4b78",
                                  "last_heard_linked": True, "changed": False})
        self.assertEqual(self.lamp.posts, [])
        self.assertFalse(self.lamp.unlocked)

    def test_an_unlinked_sender_is_reported_as_such(self):
        self.lamp.heard = "704bca112233"
        report = self.run_remotes()
        self.assertEqual((report["last_heard"], report["last_heard_linked"]), ("704bca112233", False))

    def test_a_lamp_that_heard_no_remote_reports_none(self):
        self.lamp.heard = None
        self.assertIsNone(self.run_remotes()["last_heard"])

    def test_link_replaces_the_list_keeps_espnow_and_nothing_else_changes(self):
        before = copy.deepcopy(self.lamp.cfg)
        report = self.run_remotes(link=LINKED + ["70:4B:CA:11:22:33"])
        self.assertEqual(self.lamp.posts, [{"nw": {"espnow": True, "linked_remote": LINKED + ["704bca112233"]}}])
        self.assertTrue(report["changed"])
        before["nw"]["linked_remote"] = LINKED + ["704bca112233"]
        self.assertEqual(self.lamp.cfg, before)
        self.assertFalse(self.lamp.unlocked)

    def test_link_with_the_current_list_writes_nothing(self):
        self.assertFalse(self.run_remotes(link=list(LINKED))["changed"])
        self.assertEqual(self.lamp.posts, [])

    def test_a_malformed_address_is_refused_before_any_unlock(self):
        with self.assertRaises(ValueError):
            self.run_remotes(link=["704bcac8d19"])
        self.assertEqual(self.lamp.posts, [])

    def test_another_lamp_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.run_remotes(link=LINKED + ["704bca112233"], mac="aa:bb:cc:dd:ee:ff")
        self.assertEqual(self.lamp.posts, [])

    def test_a_write_that_changes_anything_else_fails(self):
        self.lamp.side_effect = lambda cfg: cfg["light"]["gc"].update(col=2.2)
        with self.assertRaises(RuntimeError):
            self.run_remotes(link=LINKED + ["704bca112233"])
        self.assertFalse(self.lamp.unlocked)


if __name__ == "__main__":
    unittest.main()
