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


SPARES = {"fleet/overlays/spare3-gledopto.json": 3, "fleet/overlays/spare4-gledopto.json": 4,
          "fleet/overlays/spare5-domraem.json": 5, "fleet/overlays/spare6-domraem.json": 6}
# One Exoy ONE lamp per controller since 2026-11-18.
DODECA = {"fleet/overlays/exoy-links-domraem.json": "TycDodecaLinks",
          "fleet/overlays/exoy-rechts-domraem.json": "TycDodecaRechts"}
CONTROLLERS = {"curtain/h70b5-gledopto.json", "fleet/overlays/couch-domraem.json", *DODECA, *SPARES}
# Lamps whose overlay sets their name and nothing else.
NAME_ONLY = {"fleet/overlays/moon.json": "TycMoon", "fleet/overlays/glorb-links.json": "TycGlorbLinks",
             "fleet/overlays/glorb-rechts.json": "TycGlorbRechts"}
NAMES = {"curtain/h70b5-gledopto.json": "TycCurtain", "fleet/overlays/couch-domraem.json": "TycCouch",
         **DODECA, **NAME_ONLY}
# The HyperCube: its boot state only.
CUBE = "fleet/overlays/cube-gl015.json"


class Overlays(unittest.TestCase):
    """Every controller's `install --cfg` overlay (fleet/README.md, Flash and Spares)."""

    def load(self, path):
        with open(os.path.join(ROOT, path)) as f:
            return json.load(f)

    def test_every_controller_overlay_is_listed(self):
        found = {os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "fleet", "overlays", "*.json"))}
        self.assertEqual({p for p in found if not p.endswith("-presets.json")},
                         {p for p in CONTROLLERS | set(NAME_ONLY) | {CUBE} if p.startswith("fleet/overlays/")})

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

    def test_the_cube_overlay_only_sets_boot_remotes_and_cross_subnet_ota(self):
        cfg = self.load(CUBE)
        self.assertEqual(set(cfg), {"def", "nw", "ota"})
        self.assertEqual(cfg["def"], {"ps": 0, "on": False, "bri": 150})
        self.assertEqual(cfg["ota"], {"same-subnet": False})

    def test_spares_change_only_identity_boot_state_and_ota(self):
        for path, n in SPARES.items():
            self.assertEqual(self.load(path), {"id": {"name": f"TycLedSpare{n}", "mdns": f"tycledspare{n}"},
                                               "def": {"ps": 0, "on": False, "bri": 16},
                                               "ota": {"same-subnet": False},
                                               "um": {"Syslog": {"hostname": f"tycledspare{n}"}}}, path)

    def test_each_dodeca_lamp_is_one_30x16_matrix_on_gpio16_at_6000_ma(self):
        for path in DODECA:
            led = self.load(path)["hw"]["led"]
            self.assertEqual(led["total"], 480, path)
            self.assertEqual([(o["start"], o["len"], o["pin"], o["maxpwr"], o["ledma"]) for o in led["ins"]],
                             [(0, 480, [16], 6000, 55)], path)
            self.assertEqual(led["matrix"], {"mpc": 1, "panels": [{"b": False, "r": False, "v": True, "s": False,
                                                                   "x": 0, "y": 0, "h": 16, "w": 30}]}, path)

    def test_no_dodeca_lamp_takes_its_brightness_from_wled_sync(self):
        # A WLED controller that sends sync in group 1 must not set the brightness (udp.cpp; the curtain and the couch
        # receive none). It holds while the lamp receives col, fx or pal: with all four off udp.cpp takes bri anyway.
        for path in DODECA:
            self.assertEqual(self.load(path)["if"]["sync"], {"recv": {"bri": False}}, path)

    def test_no_lamp_switches_itself_on_when_power_comes_back(self):
        # Operator, 2026-11-19, on a lamp lit after a power cut: "if we have power outage this happens and this an
        # antipatern". Every controller boots off, and a boot preset carries no power of its own: the couch's 250 says
        # off, the Exoys' 250 is their calm cycle without "on", which stays dark until someone switches the lamp on
        # (playlist.cpp handlePlaylist returns while bri is 0) and then shows its first look, not one plain colour.
        boot_presets = {"fleet/overlays/couch-domraem.json": "fleet/overlays/couch-presets.json",
                        **{path: "fleet/overlays/exoy-presets.json" for path in DODECA}}
        # The cube's overlay holds its boot state and its OTA switch; outputs and presets come from tyclab/tycHyperWled.
        for path in sorted(CONTROLLERS | {CUBE}):
            start = self.load(path)["def"]
            self.assertIs(start["on"], False, path)
            if start["ps"]:
                preset = json.load(open(os.path.join(ROOT, boot_presets[path])))[str(start["ps"])]
                self.assertIsNot(preset.get("on"), True, f"{path} boot preset {start['ps']}")

    def test_each_dodeca_lamp_runs_every_scene_at_its_own_period_and_wleds_own_timer_never_comes_first(self):
        # um.Exoy.period_us 0: each scene's own frame period, the unchanged original's in the emulator
        # (tycExoyWled wled/scene-periods.tsv: 18,379 to 22,480 us, the static Custom Hue 16,000).
        # From vid 2611190 the usermod asks WLED for a frame when the lamp's next one is due, as long as WLED's
        # own frame time, 1000 // fps in ms (FX_fcn.cpp setTargetFps()), is no shorter than the scene's period:
        # WLED's timer then never shows a frame in between. An earlier image is called by that timer alone and
        # would show 40 frames a second of the engine's 44 to 62, so the overlay is for vid 2611190 and later.
        longest_period_us = 22480
        for path in DODECA:
            cfg = self.load(path)
            self.assertEqual(cfg["um"]["Exoy"], {"period_us": 0}, path)
            self.assertGreaterEqual((1000 // cfg["hw"]["led"]["fps"]) * 1000, longest_period_us, path)

    def test_each_dodeca_lamp_hears_its_own_microphone_and_no_sound_sync_runs(self):
        # Since 2026-11-20 each Exoy lamp's controller has an I2S microphone (generic I2S, type 1, SD 26, WS 5,
        # SCK 21, as the couch's DOM-WLE-ADM). AudioReactive's UDP sound sync: bit 0 sends, bit 1 receives
        # (audio_reactive.cpp, audioSyncEnabled); it is off everywhere, written as 0 because overlays are partial.
        self.assertEqual(self.load("fleet/overlays/couch-domraem.json")["um"]["AudioReactive"]["sync"], {"mode": 0})
        for path in DODECA:
            self.assertEqual(self.load(path)["um"]["AudioReactive"],
                             {"enabled": True, "digitalmic": {"type": 1, "pin": [26, 5, 21, -1]}, "sync": {"mode": 0}},
                             path)

    def test_every_overlay_that_writes_nw_pairs_the_three_remotes_with_espnow_on(self):
        remotes = ["704bcac8d198", "704bcac9aa6c", "704bcaca4b78"]
        paths = [path for path in sorted(CONTROLLERS | {CUBE}) if "nw" in self.load(path)]
        self.assertEqual(paths, ["fleet/overlays/couch-domraem.json", "fleet/overlays/cube-gl015.json",
                                 "fleet/overlays/exoy-links-domraem.json", "fleet/overlays/exoy-rechts-domraem.json"])
        for path in paths:
            self.assertEqual(self.load(path)["nw"], {"espnow": True, "linked_remote": remotes}, path)


if __name__ == "__main__":
    unittest.main()
