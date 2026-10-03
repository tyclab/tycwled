"""install --cfg: the /json/cfg body and its read-back check.

WLED 16 clears every paired ESP-NOW remote on a /json/cfg write without an "nw" block
(cfg.cpp runs linked_remotes.clear() before the null check, since PR 4654). The payload
builder carries the lamp's own espnow flag and remote list; the read-back check reports
every override the lamp did not take.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

OVERRIDES = {"light": {"gc": {"bri": 1.0, "col": 1.0, "val": 1.0}}, "hw": {"led": {"maxpwr": 2800, "fps": 42}},
             "ota": {"same-subnet": False}}
LAMP = {"nw": {"espnow": True, "linked_remote": ["4cebd6203de7"], "ins": [{"ssid": "x"}]},
        "light": {"gc": {"bri": 1, "col": 2.8, "val": 2.8}}, "hw": {"led": {"maxpwr": 3000, "fps": 42}}}


class CfgPayload(unittest.TestCase):
    def test_carries_the_lamps_remotes(self):
        body = wledlab.cfg_payload(OVERRIDES, LAMP)
        self.assertEqual(body["nw"], {"espnow": True, "linked_remote": ["4cebd6203de7"]})
        self.assertEqual(body["light"], OVERRIDES["light"])

    def test_leaves_wifi_out_of_the_body(self):
        self.assertNotIn("ins", wledlab.cfg_payload(OVERRIDES, LAMP)["nw"])

    def test_explicit_nw_in_overrides_wins(self):
        body = wledlab.cfg_payload({**OVERRIDES, "nw": {"espnow": False}}, LAMP)
        self.assertEqual(body["nw"], {"espnow": False})

    def test_no_espnow_build_adds_nothing(self):
        self.assertNotIn("nw", wledlab.cfg_payload(OVERRIDES, {"nw": {"ins": []}}))
        self.assertNotIn("nw", wledlab.cfg_payload(OVERRIDES, {}))

    def test_overrides_are_not_mutated(self):
        src = {"hw": {"led": {"fps": 42}}}
        wledlab.cfg_payload(src, LAMP)
        self.assertEqual(src, {"hw": {"led": {"fps": 42}}})


class CfgUnapplied(unittest.TestCase):
    def test_all_applied(self):
        after = {"light": {"gc": {"bri": 1, "col": 1, "val": 1}, "tr": {"dur": 7}},
                 "hw": {"led": {"maxpwr": 2800, "fps": 42, "total": 120}}, "ota": {"same-subnet": False}}
        self.assertEqual(wledlab.cfg_unapplied(OVERRIDES, after), [])

    def test_changed_and_absent_paths_are_reported(self):
        after = {"light": {"gc": {"bri": 1, "col": 2.8, "val": 1}}, "hw": {"led": {"fps": 42}}, "ota": {"same-subnet": False}}
        self.assertEqual(wledlab.cfg_unapplied(OVERRIDES, after),
                         ["light.gc.col: wanted 1.0, lamp has 2.8", "hw.led.maxpwr: wanted 2800, lamp has <absent>"])


if __name__ == "__main__":
    unittest.main()
