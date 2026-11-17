"""install --cfg: the /json/cfg body and its read-back check.

WLED 16 clears every paired ESP-NOW remote on a /json/cfg write without an "nw" block
(cfg.cpp runs linked_remotes.clear() before the null check, since PR 4654). The payload
builder carries the lamp's own espnow flag and remote list; the read-back check reports
every override the lamp did not take.
"""
import glob
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
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


SPARES = {"fleet/overlays/spare1-domraem.json": 1, "fleet/overlays/spare2-domraem.json": 2,
          "fleet/overlays/spare3-gledopto.json": 3}
CONTROLLERS = {"curtain/h70b5-gledopto.json", "fleet/overlays/couch-domraem.json",
               "fleet/overlays/exoy-gledopto.json", *SPARES}
# Lamps whose overlay sets their name and nothing else.
NAME_ONLY = {"fleet/overlays/moon.json": "TycMoon", "fleet/overlays/glorb-links.json": "TycGlorbLinks",
             "fleet/overlays/glorb-rechts.json": "TycGlorbRechts"}
NAMES = {"curtain/h70b5-gledopto.json": "TycCurtain", "fleet/overlays/couch-domraem.json": "TycCouch",
         "fleet/overlays/exoy-gledopto.json": "TycDodeca", **NAME_ONLY}


class Overlays(unittest.TestCase):
    """Every controller's `install --cfg` overlay (fleet/README.md, Flash and Spares)."""

    def load(self, path):
        with open(os.path.join(ROOT, path)) as f:
            return json.load(f)

    def test_every_controller_overlay_is_listed(self):
        found = {os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "fleet", "overlays", "*.json"))}
        self.assertEqual({p for p in found if not p.endswith("-presets.json")},
                         {p for p in CONTROLLERS | set(NAME_ONLY) if p.startswith("fleet/overlays/")})

    def test_every_lamp_in_service_has_its_tycstation_name(self):
        self.assertEqual({path: self.load(path)["id"]["name"] for path in NAMES}, NAMES)

    def test_name_only_overlays_set_nothing_but_the_name(self):
        for path, name in NAME_ONLY.items():
            self.assertEqual(self.load(path), {"id": {"name": name}}, path)

    def test_syslog_host_is_the_mdns_name_and_ota_crosses_subnets(self):
        for path in sorted(CONTROLLERS):
            cfg = self.load(path)
            self.assertEqual(cfg["um"]["Syslog"]["hostname"], cfg["id"]["mdns"], path)
            self.assertIs(cfg["ota"]["same-subnet"], False, path)

    def test_spares_change_only_identity_boot_state_and_ota(self):
        for path, n in SPARES.items():
            self.assertEqual(self.load(path), {"id": {"name": f"WLED Spare {n}", "mdns": f"tycledspare{n}"},
                                               "def": {"ps": 0, "on": False, "bri": 16},
                                               "ota": {"same-subnet": False},
                                               "um": {"Syslog": {"hostname": f"tycledspare{n}"}}}, path)


if __name__ == "__main__":
    unittest.main()
