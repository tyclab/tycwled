"""cfg_drift: which cfg changes a firmware flash may cause without counting as drift."""
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
