"""install --cfg: the /json/cfg body and its read-back check.

WLED 16 clears every paired ESP-NOW remote on a /json/cfg write without an "nw" block
(cfg.cpp runs linked_remotes.clear() before the null check, since PR 4654). The payload
builder carries the lamp's own espnow flag and remote list; the read-back check reports
every override the lamp did not take.
"""
import glob
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import wledlab  # noqa: E402

OVERRIDES = {"light": {"gc": {"bri": 1.0, "col": 1.0, "val": 1.0}}, "hw": {"led": {"maxpwr": 2800, "fps": 42}},
             "ota": {"same-subnet": False}}
LAMP = {"nw": {"espnow": True, "linked_remote": ["00005e00530a"], "ins": [{"ssid": "example"}]},
        "light": {"gc": {"bri": 1, "col": 2.8, "val": 2.8}}, "hw": {"led": {"maxpwr": 3000, "fps": 42}}}


class CfgPayload(unittest.TestCase):
    def test_carries_the_lamps_remotes(self):
        body = wledlab.cfg_payload(OVERRIDES, LAMP)
        self.assertEqual(body["nw"], {"espnow": True, "linked_remote": ["00005e00530a"]})
        self.assertEqual(body["light"], OVERRIDES["light"])

    def test_explicit_nw_in_overrides_wins(self):
        body = wledlab.cfg_payload({**OVERRIDES, "nw": {"espnow": False}}, LAMP)
        self.assertEqual(body["nw"], {"espnow": False})


class CfgUnapplied(unittest.TestCase):
    def test_all_applied(self):
        after = {"light": {"gc": {"bri": 1, "col": 1, "val": 1}, "tr": {"dur": 7}},
                 "hw": {"led": {"maxpwr": 2800, "fps": 42, "total": 120}}, "ota": {"same-subnet": False}}
        self.assertEqual(wledlab.cfg_unapplied(OVERRIDES, after), [])

    def test_changed_and_absent_paths_are_reported(self):
        after = {"light": {"gc": {"bri": 1, "col": 2.8, "val": 1}}, "hw": {"led": {"fps": 42}}, "ota": {"same-subnet": False}}
        self.assertEqual(wledlab.cfg_unapplied(OVERRIDES, after),
                         ["light.gc.col: wanted 1.0, lamp has 2.8", "hw.led.maxpwr: wanted 2800, lamp has <absent>"])


# One Exoy ONE lamp per controller since 2026-11-18.
DODECA = {"fleet/overlays/exoy-links-domraem.json": "TycDodecaLinks",
          "fleet/overlays/exoy-rechts-domraem.json": "TycDodecaRechts"}
CURTAIN = "curtain/h70b5-gledopto.json"


class Overlays(unittest.TestCase):
    """Every `install --cfg` overlay: the curtain's and fleet/overlays/*.json (fleet/README.md, Flash and Spares)."""

    def load(self, path):
        with open(os.path.join(ROOT, path)) as f:
            return json.load(f)

    def overlays(self):
        # One that sets only the lamp's name (the Moon's, the GLORBs') writes nothing a rule reads.
        found = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "fleet", "overlays", "*.json"))
                       if not p.endswith("-presets.json"))
        self.assertTrue(found, "no overlay in fleet/overlays")
        cfgs = [(path, self.load(path)) for path in [CURTAIN, *found]]
        return [(path, cfg) for path, cfg in cfgs if cfg != {"id": {"name": cfg.get("id", {}).get("name")}}]

    def test_syslog_host_is_the_mdns_name_and_ota_crosses_subnets(self):
        # An overlay that sets the lamp's identity names its mDNS name and the same syslog host; the cube's sets none.
        # tycpve's flash uploads from another subnet, and WLED refuses that upload while same-subnet is true.
        for path, cfg in self.overlays():
            if "id" in cfg:
                self.assertEqual(cfg["um"]["Syslog"]["hostname"], cfg["id"]["mdns"], path)
            self.assertIs(cfg.get("ota", {}).get("same-subnet"), False, path)

    def test_every_dodeca_output_is_limited_to_at_most_6_a(self):
        # 6000 mA per lamp at 55 mA per LED is the limit of 2026-11-18 (480 LEDs on one supply, fleet/README.md). WLED
        # 16.0.1 scales its estimate by the LED current (255: its 12 mA WS2815 model), and a global limit above 0 takes
        # the place of the per-output ones. Bounds: a lower limit or a higher LED current passes; none (0), a higher
        # limit, a lower LED current and 255 do not.
        for path in DODECA:
            led = self.load(path)["hw"]["led"]
            self.assertLessEqual(led["maxpwr"], 6000, path)
            for output in led["ins"]:
                self.assertTrue(0 < output["maxpwr"] <= 6000, (path, output["maxpwr"]))
                self.assertTrue(55 <= output["ledma"] < 255, (path, output["ledma"]))

    def test_every_output_an_overlay_writes_limits_its_current(self):
        # WLED 16.0.1 (bus_manager.cpp): an LED current of 0 turns an output's limiter off, and a global limit above 0
        # takes the place of the per-output ones. So each output has an LED current above 0 and a limit above 0, its
        # own or the global one.
        for path, cfg in self.overlays():
            led = cfg.get("hw", {}).get("led", {})
            for output in led.get("ins", []):
                self.assertTrue(output["ledma"] > 0 and max(led["maxpwr"], output["maxpwr"]) > 0, (path, output))

    def test_no_lamp_switches_itself_on_when_power_comes_back(self):
        # Operator, 2026-11-19, on a lamp lit after a power cut: "if we have power outage this happens and this an
        # antipatern". Every controller boots off, and a boot preset carries no power of its own: the couch's 250 says
        # off, the Exoys' 250 is their calm cycle without "on", which stays dark until someone switches the lamp on
        # (playlist.cpp handlePlaylist returns while bri is 0) and then shows its first look, not one plain colour.
        boot_presets = {"fleet/overlays/couch-domraem.json": "fleet/overlays/couch-presets.json",
                        **{path: "fleet/overlays/exoy-presets.json" for path in DODECA}}
        # The cube's overlay holds its boot state and its OTA switch; outputs and presets come from tyclab/tycHyperWled.
        for path, cfg in self.overlays():
            start = cfg.get("def", {})
            self.assertIs(start.get("on"), False, path)
            if start.get("ps"):
                preset = json.load(open(os.path.join(ROOT, boot_presets[path])))[str(start["ps"])]
                self.assertIsNot(preset.get("on"), True, f"{path} boot preset {start['ps']}")

    def test_every_overlay_that_writes_nw_pairs_the_same_three_remotes_with_espnow_on(self):
        # Which lamps carry the remotes in their overlay is a fact of the hardware; no pairing list lives here.
        overlays = dict(self.overlays())
        paths = [path for path in sorted(overlays) if "nw" in overlays[path]]
        self.assertEqual(paths, ["fleet/overlays/couch-domraem.json", "fleet/overlays/cube-gl015.json",
                                 "fleet/overlays/exoy-links-domraem.json", "fleet/overlays/exoy-rechts-domraem.json"])
        remotes = overlays[paths[0]]["nw"]["linked_remote"]
        self.assertEqual(len(set(remotes)), 3)
        self.assertTrue(all(re.fullmatch("[0-9a-f]{12}", remote) for remote in remotes), paths[0])
        for path in paths:
            self.assertEqual(overlays[path]["nw"], {"espnow": True, "linked_remote": remotes}, path)


if __name__ == "__main__":
    unittest.main()
