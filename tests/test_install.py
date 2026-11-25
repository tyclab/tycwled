"""install: extra files, the liveview check on animated GIFs, and the look put back afterwards."""
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def segment(fx, name=""):
    return {"id": 0, "start": 0, "stop": 68, "fx": fx, "sx": 128, "ix": 0, "pal": 0, "bri": 255, "n": name}


class Lamp:
    """A controller that stores uploads, recalls presets and plays a GIF only when it holds the file. As WLED 16.0.1
    does (json.cpp, led.cpp, presets.cpp, playlist.cpp): "ps" names the preset shown unchanged, a segment write clears
    it unless "pd" names it, and "transition" stays as the lamp's setting while "tt" applies once. A preset that holds
    a playlist starts it: the lamp reports its id as "pl" and shows the playlist's first entry. Recalling a preset or
    writing a segment with an effect ends a running playlist. A segment write sets the fields it names on the segment
    with its id.

    The Image effect as WLED 16.0.1 runs it (wled.cpp, FX_fcn.cpp, image_loader.cpp, AnimatedGIF 1.4.7 on littlefs):
    the lamp draws while it is on, or once after a write that changed the state; a new effect resets the segment and
    ends the playback; a draw of the Image effect opens its file when the segment's name differs from the open one and
    otherwise reads on through the open handle. A file replaced under that handle keeps its old bytes for it, while
    the decoder's size comes from the path: at the old end it reads short, fails, and the segment stands still until
    its name changes or it is reset."""

    def __init__(self):
        self.files, self.calls, self.frozen, self.deaf, self.stuck, self.drops, self.mute = {}, [], False, False, False, 0, 0
        self.live_stream, self.restarts, self.nameless = False, 0, False
        # The Image effect's open file: its name, the bytes its handle reads, and whether decoding has failed. Also
        # a house rule that switches the lamp off again whenever something switches it on.
        self.decoder, self.switched_off_again = None, False
        # Custom palettes as loadCustomPalettes (colors.cpp) left them, and how many deletes the filesystem loses.
        self.palettes, self.lost, self.keeps_list = 0, 0, False
        self.state = {"on": True, "bri": 100, "ps": -1, "pl": -1, "transition": 7, "seg": [segment(191)]}
        # /json/cfg as tycdodeca serves it, cut to what the tests read (cfg.cpp serializeConfig).
        self.cfg = {"id": {"mdns": "tycdodeca", "name": "Exoy"}, "nw": {"espnow": True, "linked_remote": ["00005e00530a"]},
                    "ota": {"lock": True, "lock-wifi": True, "aota": False, "same-subnet": True}, "wifi": {"sleep": False},
                    "def": {"ps": 0, "on": False, "bri": 128},
                    "hw": {"led": {"total": 960, "maxpwr": 0, "ins": [{"start": 0, "len": 480, "pin": [16], "maxpwr": 5000, "ledma": 55},
                                                                    {"start": 480, "len": 480, "pin": [12], "maxpwr": 5500, "ledma": 55}]}}}
        # What the radio and the network run with: taken from the stored cfg only when the lamp connects (wled.cpp
        # initConnection, initInterfaces), so after a restart.
        self.running = self.connect_settings()

    def connect_settings(self):
        return {".".join(path): wledlab._connect_value(self.cfg, path) for path in wledlab.CONNECT_ONLY}

    def upload(self, host, name, path, timeout=30):
        self.calls.append(("upload", name))
        raw = open(path, "rb").read()
        if name == "/presets.json" and self.drops:
            # The connection drops part-way (curl exit 52): the lamp keeps what had arrived, a cut-off file.
            self.drops -= 1
            self.files[name] = raw[:len(raw) // 3]
            raise RuntimeError(f"upload {path} -> lamp{name}: curl exit 52")
        self.files[name] = raw
        if name == "/presets.json" and self.mute:
            # The whole file is written and the connection closes without an answer (tycdodeca, 2026-11-11).
            self.mute -= 1
            raise RuntimeError(f"upload {path} -> lamp{name}: curl exit 52")
        return "ok"

    def readback(self, host, name, timeout=10):
        return self.files.get(name, b"")

    def load_palettes(self):
        """colors.cpp loadCustomPalettes: one entry per slot up to the highest that holds a file."""
        slots = [int(name[len("/palette"):-len(".json")]) for name in self.files if name.startswith("/palette")]
        self.palettes = max(slots) + 1 if slots else 0

    def settings_request(self, host, path, fields=None):
        if path != "/settings/sec":
            return 200 if path in self.files else 404
        # set.cpp handleSettingsSet, security page: the PIN opens the settings; the four OTA switches are taken
        # with the OTA password, each on when its field is sent.
        self.calls.append(("sec", sorted(fields or {})))
        if fields and fields.get("PIN") == PIN and "OP" not in fields:
            self.open = True
        if not getattr(self, "open", False):
            return 401
        if fields and fields.get("OP") == OTA_PASSWORD:
            self.cfg["ota"].update({key: field in fields for key, field in wledlab.OTA_SWITCHES.items()})
        return 200

    def get(self, host, path):
        if path == "/json/info":
            return {"ver": "16.0.1", "leds": {}, "cpalcount": self.palettes, "live": self.live_stream}
        if path == "/json/cfg":
            return copy.deepcopy(self.cfg)
        state = copy.deepcopy(self.state)
        state["seg"] = [{k: v for k, v in seg.items() if k != "n" or v} for seg in state["seg"]]
        return state

    def post(self, host, path, body):
        self.calls.append(("post", copy.deepcopy(body)))
        if path == "/json/cfg":
            # cfg.cpp deserializeConfig: the paired remotes are cleared before the body is looked at, and a body
            # that names the outputs replaces them all.
            self.cfg["nw"]["linked_remote"] = body.get("nw", {}).get("linked_remote", [])
            # CJSON keeps a setting the body does not name: the ESP-NOW switch and the Wi-Fi sleep mode.
            self.cfg["nw"]["espnow"] = body.get("nw", {}).get("espnow", self.cfg["nw"]["espnow"])
            self.cfg["wifi"]["sleep"] = body.get("wifi", {}).get("sleep", self.cfg["wifi"]["sleep"])
            self.cfg["id"].update(body.get("id", {}))
            led = body.get("hw", {}).get("led", {})
            self.cfg["hw"]["led"].update(copy.deepcopy(led))
            # cfg.cpp deserializeConfig: the OTA switches are heard only with the OTA lock off.
            if not self.cfg["ota"]["lock"]:
                self.cfg["ota"].update({k: v for k, v in body.get("ota", {}).items() if k in wledlab.OTA_SWITCHES})
        elif body.get("rb"):
            # A restart: the lamp connects with what its cfg holds, boots into its "def" state with no preset and
            # forgets the settings PIN's session.
            self.restarts += 1
            self.running, self.open = self.connect_settings(), False
            boot = self.cfg["def"]
            self.state = {"on": boot["on"], "bri": boot["bri"], "ps": -1, "pl": -1, "transition": 7, "seg": [segment(0)]}
        elif "rmcpal" in body:
            # json.cpp deserializeState: the file is removed if it is there, the result is not looked at, and the
            # custom palettes are loaded again. Nothing else of the state changes.
            if self.lost:
                self.lost -= 1
            else:
                self.files.pop(f"/palette{body['rmcpal']}.json", None)
            if not self.keeps_list:
                self.load_palettes()
        elif "ps" in body:
            changed = self.look()
            presets = json.loads(self.files["/presets.json"])
            preset, playlist = presets[str(body["ps"])], -1
            self.state.update(on=body.get("on", self.state["on"]), bri=body.get("bri", self.state["bri"]))
            if "playlist" in preset and not self.stuck:
                playlist, preset = body["ps"], presets[str(preset["playlist"]["ps"][0])]
            if "seg" in preset:
                # A preset is applied as a state body of its own (presets.cpp, json.cpp deserializeState): its "on"
                # wins over the recall's.
                self.state.update(on=preset.get("on", True), ps=body["ps"] if playlist < 0 else presets[str(playlist)]["playlist"]["ps"][0],
                                  seg=copy.deepcopy(preset["seg"]))
            self.state["pl"] = playlist
            self.drew(changed)
        elif "seg" in body and not self.deaf:
            changed = self.look()
            if any("fx" in seg for seg in body["seg"]):
                self.state["pl"] = -1
            segs = copy.deepcopy(self.state["seg"])
            for n, write in enumerate(body["seg"]):
                old = next((seg for seg in segs if seg.get("id") == write.get("id", n)), None)
                if old is None:
                    segs.append(copy.deepcopy(write))
                else:
                    name = old.get("n", "")
                    old.update(copy.deepcopy(write))
                    if self.nameless:
                        # The names do not take: each segment keeps the GIF it played.
                        old["n"] = name
            self.state.update(on=body.get("on", self.state["on"]), bri=body.get("bri", self.state["bri"]),
                              ps=body.get("pd", -1), seg=segs, transition=body.get("transition", self.state["transition"]))
            self.drew(changed)

    def look(self):
        return copy.deepcopy((self.state["on"], self.state["bri"], [seg.get("fx") for seg in self.state["seg"]]))

    def drew(self, before):
        """After a write: a house rule may switch the lamp off again; the lamp draws if it is on or the write changed
        its power, brightness or an effect (stateUpdated triggers a draw)."""
        if self.switched_off_again and self.state["on"]:
            self.state["on"] = False
        if self.state["on"] or self.look() != before:
            self.draw()

    def draw(self):
        seg = self.state["seg"][0] if self.state["seg"] else {}
        if seg.get("fx") != 53:  # FX_MODE_IMAGE (FX.h)
            self.decoder = None
            return
        name = "/" + seg.get("n", "")
        if self.decoder is None or self.decoder["name"] != name:
            self.decoder = {"name": name, "bytes": self.files.get(name, b""), "failed": False}
        elif len(self.files.get(name, b"")) != len(self.decoder["bytes"]):
            self.decoder["failed"] = True

    def live(self, host, seconds):
        self.drew(self.look())
        d = self.decoder
        moving = self.state["on"] and d and not d["failed"] and not self.frozen
        frames = wledlab.gif_frames(d["bytes"]) if moving else 1
        return [(i / 10, [f"{i % max(frames, 1):06x}"]) for i in range(10)]


PIN, OTA_PASSWORD = "4872", "0123456789abcdef0123456789abcdef"


class Install(unittest.TestCase):
    def setUp(self):
        self.lamp = Lamp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.presets = os.path.join(directory.name, "presets.json")
        with open(self.presets, "w") as f:
            json.dump({"0": {}, "1": {"n": "Still", "seg": [segment(53, "tycstation.gif")]},
                       "4": {"n": "Loop", "seg": [segment(53, "squid-eyes.gif")]}}, f)
        self.args = SimpleNamespace(host="lamp", ledmap=None, palette=None, cfg=None, reboot=False, effects=None, remote=None, presets=self.presets,
                                    file=[os.path.join(ROOT, "curtain", "squid-eyes.gif")], restore=True)
        for name in ("upload", "readback", "get", "post", "live", "settings_request"):
            patcher = patch.object(wledlab, name, getattr(self.lamp, name))
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(wledlab.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def cfg_file(self, overrides):
        path = os.path.join(os.path.dirname(self.presets), "cfg.json")
        with open(path, "w") as f:
            json.dump(overrides, f)
        self.args.presets, self.args.file, self.args.cfg = None, [], path

    def test_cfg_the_lamp_does_not_hold_is_written_with_its_remotes_and_read_back(self):
        outputs = [dict(o, maxpwr=6000) for o in self.lamp.cfg["hw"]["led"]["ins"]]
        self.cfg_file({"hw": {"led": {"maxpwr": 0, "ins": outputs}}})
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [("post", {"hw": {"led": {"maxpwr": 0, "ins": outputs}},
                                                     "nw": {"espnow": True, "linked_remote": ["00005e00530a"]}})])
        self.assertEqual(([o["maxpwr"] for o in self.lamp.cfg["hw"]["led"]["ins"]], self.lamp.cfg["nw"]["linked_remote"]),
                         ([6000, 6000], ["00005e00530a"]))

    def test_a_name_only_overlay_writes_the_name_and_leaves_the_outputs_alone(self):
        outputs = copy.deepcopy(self.lamp.cfg["hw"]["led"]["ins"])
        self.cfg_file({"id": {"name": "TycMoon"}})
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [("post", {"id": {"name": "TycMoon"},
                                                     "nw": {"espnow": True, "linked_remote": ["00005e00530a"]}})])
        self.assertEqual((self.lamp.cfg["id"], self.lamp.cfg["hw"]["led"]["ins"]),
                         ({"mdns": "tycdodeca", "name": "TycMoon"}, outputs))

    def test_an_overlay_that_names_the_remotes_pairs_them_and_reads_them_back(self):
        # TycDodecaLinks, 2026-11-18: a new controller with no remote got its list from the overlay, and the install
        # ended red on the change it was asked to make.
        remotes = ["00005e00530a", "00005e00530b", "00005e00530c"]
        self.cfg_file({"nw": {"espnow": True, "linked_remote": remotes}})
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [("post", {"nw": {"espnow": True, "linked_remote": remotes}})])
        self.assertEqual(self.lamp.cfg["nw"]["linked_remote"], remotes)

    def test_an_overlay_that_turns_espnow_on_restarts_the_lamp_once_and_puts_its_look_back(self):
        # TycDodecaLinks and TycDodecaRechts, 2026-11-20: they came with ESP-NOW off, the install turned it on, and
        # neither heard a remote until it was restarted (WLED starts ESP-NOW only when it connects).
        remotes = ["00005e00530a", "00005e00530b", "00005e00530c"]
        self.lamp.cfg["nw"] = {"espnow": False, "linked_remote": [""]}
        self.lamp.running = self.lamp.connect_settings()
        shown = copy.deepcopy(self.lamp.state)
        self.cfg_file({"nw": {"espnow": True, "linked_remote": remotes}})
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.restarts, self.lamp.running["nw.espnow"], self.lamp.cfg["nw"]),
                         (1, True, {"espnow": True, "linked_remote": remotes}))
        self.assertEqual((self.lamp.state["on"], self.lamp.state["bri"], self.lamp.state["seg"][0]["fx"]),
                         (shown["on"], shown["bri"], shown["seg"][0]["fx"]))
        # A new mDNS name, which the spare overlays write, takes one more restart (a new run: the install set reboot).
        self.args.reboot = False
        self.cfg_file({"id": {"mdns": "tycledspare5"}})
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.restarts, self.lamp.running["id.mdns"]), (2, "tycledspare5"))

    def test_an_explicit_reboot_with_an_espnow_change_restarts_once(self):
        self.lamp.cfg["nw"] = {"espnow": False, "linked_remote": [""]}
        self.cfg_file({"nw": {"espnow": True, "linked_remote": ["00005e00530a"]}})
        self.args.reboot = True
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.restarts, self.lamp.running["nw.espnow"]), (1, True))

    def test_a_lamp_that_already_has_espnow_on_is_not_restarted(self):
        self.cfg_file({"id": {"name": "TycMoon"}})
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.restarts, 0)

    def test_a_lamp_playing_a_live_stream_gets_nothing_and_the_next_run_after_the_show_restarts_it(self):
        self.lamp.cfg["nw"] = {"espnow": False, "linked_remote": [""]}
        self.lamp.running = self.lamp.connect_settings()
        self.lamp.live_stream = True
        self.cfg_file({"nw": {"espnow": True, "linked_remote": ["00005e00530a"]}})
        with self.assertRaises(SystemExit) as stopped:
            wledlab._cmd_install(self.args)
        self.assertIn("plays a live stream: nothing written", str(stopped.exception))
        self.assertEqual((self.lamp.restarts, self.lamp.cfg["nw"]["espnow"], self.lamp.calls), (0, False, []))
        self.lamp.live_stream = False
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.restarts, self.lamp.running["nw.espnow"]), (1, True))

    def test_a_remote_list_the_write_dropped_fails_the_install(self):
        # A body without the lamp's remotes makes WLED 16 clear them; the read-back must catch that.
        self.cfg_file({"id": {"name": "TycMoon"}})
        with patch.object(wledlab, "cfg_payload", lambda overrides, lamp: copy.deepcopy(overrides)), \
                self.assertRaises(SystemExit) as stopped:
            wledlab._cmd_install(self.args)
        self.assertEqual(str(stopped.exception), "cfg overrides did not land as written")
        self.assertEqual(self.lamp.cfg["nw"]["linked_remote"], [])

    def test_an_ota_switch_of_a_locked_lamp_goes_through_the_security_form_and_keeps_the_locks(self):
        # tycdodeca, 2026-11-17: the outputs' limits landed, `ota.same-subnet` did not, and the install ended red.
        outputs = [dict(o, maxpwr=6500) for o in self.lamp.cfg["hw"]["led"]["ins"]]
        self.cfg_file({"hw": {"led": {"maxpwr": 0, "ins": outputs}}, "ota": {"same-subnet": False}})
        access = wledlab.SettingsAccess("lamp", {"pin": PIN, "ota_password": OTA_PASSWORD})
        wledlab._cmd_install(self.args, access)
        self.assertEqual(self.lamp.cfg["ota"], {"lock": True, "lock-wifi": True, "aota": False, "same-subnet": False})
        self.assertEqual([o["maxpwr"] for o in self.lamp.cfg["hw"]["led"]["ins"]], [6500, 6500])
        self.assertEqual([call for call in self.lamp.calls if call[0] == "sec"][-1], ("sec", ["NO", "OP", "OW"]))

    def test_an_ota_switch_a_locked_lamp_keeps_fails_the_install_without_credentials(self):
        self.cfg_file({"ota": {"same-subnet": False}})
        with self.assertRaises(SystemExit) as stopped:
            wledlab._cmd_install(self.args)
        self.assertEqual(str(stopped.exception), "cfg overrides did not land as written")
        self.assertTrue(self.lamp.cfg["ota"]["same-subnet"])

    def test_cfg_the_lamp_already_reads_back_is_not_written(self):
        # A write that names the outputs rebuilds them on the lamp and restarts every effect.
        self.cfg_file({"hw": {"led": {"maxpwr": 0, "ins": copy.deepcopy(self.lamp.cfg["hw"]["led"]["ins"])}}})
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [])

    def test_counts_the_images_of_a_gif(self):
        for name, frames in (("tycstation.gif", 1), ("squid-eyes.gif", 200), ("squid-ink.gif", 120)):
            with open(os.path.join(ROOT, "curtain", name), "rb") as f:
                self.assertEqual(wledlab.gif_frames(f.read()), frames, name)
        self.assertEqual(wledlab.gif_frames(b"not a gif"), 0)

    def test_files_go_up_before_the_presets_and_the_look_comes_back(self):
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"], ["/squid-eyes.gif", "/presets.json"])
        # The whole state, so also the lamp's own transition time: the look goes back with the one-shot "tt".
        self.assertEqual(self.lamp.state, before)
        self.assertEqual(self.lamp.calls[-1][1]["tt"], 0)

    def test_a_look_that_was_a_preset_comes_back_as_that_preset(self):
        # Home Assistant reads the look from the preset the lamp reports; a bare segment write would report none.
        presets = json.load(open(self.presets))
        self.lamp.files["/presets.json"] = json.dumps(presets | {"4": {"n": "Older", "seg": [segment(1)]}}).encode()
        self.lamp.state.update(ps=1, seg=copy.deepcopy(presets["1"]["seg"]))
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state, before)
        self.assertEqual(self.lamp.calls[-1][1]["pd"], 1)

    def test_reordering_presets_restores_the_look_with_its_new_number(self):
        old = json.load(open(self.presets))
        self.lamp.files["/presets.json"] = json.dumps(old).encode()
        self.lamp.state.update(ps=1, seg=copy.deepcopy(old["1"]["seg"]))
        before = copy.deepcopy(self.lamp.state)
        with open(self.presets, "w") as f:
            json.dump({"0": {}, "1": old["4"], "7": old["1"]}, f)
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state, before | {"ps": 7})
        self.assertEqual(self.lamp.calls[-1][1]["pd"], 7)

    def test_removing_a_preset_keeps_its_look_without_claiming_the_reused_slot(self):
        old = {"1": {"n": "Removed", "seg": [segment(191)]}}
        self.lamp.files["/presets.json"] = json.dumps(old).encode()
        self.lamp.state["ps"] = 1
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state, before | {"ps": -1})
        self.assertNotIn("pd", self.lamp.calls[-1][1])

    def test_changing_a_running_playlist_refuses_before_any_upload(self):
        self.lamp.files["/presets.json"] = json.dumps({"20": {"playlist": {"ps": [1, 4]}}}).encode()
        self.lamp.state["pl"] = 20
        with self.assertRaisesRegex(SystemExit, "running playlist"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [])

    def test_an_upload_that_breaks_off_is_sent_again(self):
        self.lamp.drops = 2
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"].count("/presets.json"), 3)
        self.assertEqual(json.loads(self.lamp.files["/presets.json"]), json.load(open(self.presets)))
        self.assertEqual(self.lamp.state, before)

    def test_an_upload_the_lamp_wrote_without_answering_counts(self):
        self.lamp.mute = 1
        wledlab._cmd_install(self.args)
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"].count("/presets.json"), 1)
        self.assertIn(("post", {"on": True, "ps": 4}), self.lamp.calls)

    def test_the_same_presets_in_another_form_are_sent_compact_once_and_not_recalled(self):
        presets = json.load(open(self.presets))
        wledlab._cmd_install(self.args)
        self.lamp.files["/presets.json"] = json.dumps(presets, indent=2).encode()
        before, self.lamp.calls = copy.deepcopy(self.lamp.state), []
        wledlab._cmd_install(self.args)
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"], ["/presets.json"])
        self.assertEqual(self.lamp.files["/presets.json"], json.dumps(presets, separators=(",", ":")).encode())
        self.assertEqual(([c for c in self.lamp.calls if c[0] == "post"], self.lamp.state), ([], before))
        self.lamp.calls = []
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [])

    def test_presets_that_never_arrive_put_the_earlier_ones_back_and_recall_nothing(self):
        earlier = {"0": {}, "1": {"n": "Earlier", "seg": [segment(9)]}}
        self.lamp.files["/presets.json"] = json.dumps(earlier).encode()
        self.lamp.drops = 3
        with self.assertRaisesRegex(SystemExit, "did not arrive"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.files["/presets.json"], json.dumps(earlier, separators=(",", ":")).encode())
        self.assertEqual([c for c in self.lamp.calls if c[0] == "post"], [])

    def with_playlist(self):
        presets = json.load(open(self.presets)) | {"20": {"n": "Cycle", "on": True, "playlist": {"ps": [4, 1], "dur": [300, 300], "r": 0, "end": 0}}}
        with open(self.presets, "w") as f:
            json.dump(presets, f)
        return presets

    def test_a_playlist_is_checked_by_the_lamp_playing_it_and_does_not_outlive_the_install(self):
        # A playlist holds no segments (tycdodeca's presets 20 to 22); left running it would switch a lamp
        # that was off back on with its next entry.
        self.with_playlist()
        self.lamp.state["on"] = False
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertIn(("post", {"on": True, "ps": 20}), self.lamp.calls)
        self.assertEqual(self.lamp.state, before)

    def test_a_playlist_the_lamp_does_not_start_fails_and_the_look_still_comes_back(self):
        self.with_playlist()
        before, self.lamp.stuck = copy.deepcopy(self.lamp.state), True
        with self.assertRaisesRegex(SystemExit, r"presets \['20'\]"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state, before)

    def test_a_lamp_that_played_a_playlist_plays_it_again(self):
        presets = self.with_playlist()
        self.lamp.files["/presets.json"] = json.dumps(presets | {"9": {"n": "Older", "seg": [segment(1)]}}).encode()
        self.lamp.state.update(pl=20, ps=4, seg=copy.deepcopy(presets["4"]["seg"]))
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls[-1][1], {"on": True, "bri": 100, "tt": 0, "ps": 20})
        self.assertEqual((self.lamp.state["pl"], self.lamp.state["on"], self.lamp.state["bri"]), (20, True, 100))

    def test_a_file_that_reads_back_differently_stops_before_the_presets(self):
        with patch.object(wledlab, "readback", lambda host, name, timeout=10: b"truncated"), self.assertRaises(SystemExit):
            wledlab._cmd_install(self.args)
        self.assertNotIn(("upload", "/presets.json"), self.lamp.calls)

    def test_a_loop_that_stands_still_fails_and_the_look_still_comes_back(self):
        before, self.lamp.frozen = copy.deepcopy(self.lamp.state), True
        with self.assertRaisesRegex(SystemExit, r"presets \['4'\]"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state, before)

    def test_a_look_that_does_not_come_back_fails(self):
        self.lamp.deaf = True
        with self.assertRaisesRegex(SystemExit, "did not come back"):
            wledlab._cmd_install(self.args)

    def test_a_look_that_comes_back_with_another_gif_fails(self):
        # Two Image looks differ only in the segment's name, the GIF it plays: the check of the look put back must
        # read the name, or the last recalled preset's GIF stays on the lamp under "look restored: OK".
        self.lamp.state["seg"], self.lamp.nameless = [segment(53, "tycstation.gif")], True
        with self.assertRaisesRegex(SystemExit, "did not come back"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state["seg"][0]["n"], "squid-eyes.gif")

    def test_a_look_without_a_name_comes_back_without_one(self):
        # WLED reports no "n" for a segment without a name (json.cpp serializeSegment); the restore writes "" for it.
        self.lamp.state["seg"] = [{k: v for k, v in segment(191).items() if k != "n"}]
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls[-1][1]["seg"][0]["n"], "")
        self.assertEqual(wledlab.get("lamp", "/json/state")["seg"], before["seg"])

    def playing_an_older_squid_eyes(self, on):
        # The lamp plays an earlier squid-eyes.gif of another length, the first preset walked shows the same file, and
        # nothing between the upload and that preset changes the segment's name or effect (2026-11-24 21:11).
        with open(os.path.join(ROOT, "curtain", "squid-ink.gif"), "rb") as f:
            self.lamp.files["/squid-eyes.gif"] = f.read()
        self.lamp.state.update(on=on, seg=[segment(53, "squid-eyes.gif")])
        self.lamp.draw()
        presets = json.load(open(self.presets))
        with open(self.presets, "w") as f:
            json.dump({"0": {}, "4": presets["4"], "1": presets["1"]}, f)

    def assert_replaced_with_its_playback_ended(self, on):
        self.playing_an_older_squid_eyes(on)
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        with open(os.path.join(ROOT, "curtain", "squid-eyes.gif"), "rb") as f:
            self.assertEqual(self.lamp.decoder["bytes"], f.read())
        self.assertFalse(self.lamp.decoder["failed"])
        self.assertEqual(self.lamp.state, before)
        upload = self.lamp.calls.index(("upload", "/squid-eyes.gif"))
        self.assertIn(("post", {"tt": 0, "seg": [{"id": 0, "fx": 0}]}), self.lamp.calls[:upload])

    def test_a_gif_a_lit_lamp_plays_is_not_replaced_under_its_decoder(self):
        self.assert_replaced_with_its_playback_ended(on=True)

    def test_a_gif_a_lamp_that_is_off_holds_open_is_not_replaced_under_its_decoder(self):
        self.assert_replaced_with_its_playback_ended(on=False)

    def test_a_lamp_switched_off_during_the_check_says_so(self):
        # 2026-11-24 21:11: Home Assistant's Away rule switched the GLORB off about 70 ms after each recall.
        self.lamp.switched_off_again = True
        with self.assertRaisesRegex(SystemExit, "switched off during the check"):
            wledlab._cmd_install(self.args)

    def test_a_preset_that_switches_the_lamp_off_is_not_taken_for_a_lamp_switched_off(self):
        # 2026-11-25: the couch's preset 250 "Boot layout (off)" carries "on": false and failed the check above.
        presets = json.load(open(self.presets)) | {"250": {"n": "Boot layout (off)", "on": False, "seg": [segment(191)]}}
        with open(self.presets, "w") as f:
            json.dump(presets, f)
        before = copy.deepcopy(self.lamp.state)
        wledlab._cmd_install(self.args)
        self.assertIn(("post", {"on": True, "ps": 250}), self.lamp.calls)
        self.assertEqual(self.lamp.state, before)

    def test_files_and_presets_already_on_the_lamp_are_not_sent_or_recalled(self):
        wledlab._cmd_install(self.args)
        before, self.lamp.calls = copy.deepcopy(self.lamp.state), []
        self.args.file = self.args.file + [os.path.join(ROOT, "curtain", "squid-ink.gif")]
        wledlab._cmd_install(self.args)
        # Only the new file goes up; no preset shows it, so none is recalled and the look is not touched.
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"], ["/squid-ink.gif"])
        self.assertEqual([c for c in self.lamp.calls if c[0] == "post"], [])
        self.assertEqual(self.lamp.state, before)

    def with_palettes(self, *slots):
        for slot in slots:
            self.lamp.files[f"/palette{slot}.json"] = b'{"palette":[0,0,0,0,255,255,255,255]}'
        self.lamp.load_palettes()
        self.args.presets, self.args.restore, self.args.file = None, False, None

    def test_a_removed_palette_is_gone_and_the_lamps_list_follows(self):
        self.with_palettes(0)
        self.lamp.state.update(on=False, ps=3)
        before, self.args.remove_palette = copy.deepcopy(self.lamp.state), [0]
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.files, self.lamp.palettes), ({}, 0))
        self.assertEqual([c for c in self.lamp.calls if c[0] == "post"], [("post", {"rmcpal": 0})])
        # WLED's removal leaves power, brightness and the preset marker alone, and so does the tool.
        self.assertEqual(self.lamp.state, before)

    def test_a_palette_after_the_ports_six_goes_and_the_six_stay(self):
        # The GLORBs: palette0 to palette5 are the port's, palette6 was the TycStation one.
        self.with_palettes(*range(7))
        self.args.remove_palette = [6]
        wledlab._cmd_install(self.args)
        self.assertEqual((sorted(self.lamp.files), self.lamp.palettes), ([f"/palette{n}.json" for n in range(6)], 6))

    def test_a_palette_that_is_not_on_the_lamp_sends_nothing(self):
        self.with_palettes()
        self.args.remove_palette = [0]
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [])

    def test_a_delete_the_lamp_loses_is_sent_again(self):
        self.with_palettes(0)
        self.lamp.lost, self.args.remove_palette = 2, [0]
        wledlab._cmd_install(self.args)
        self.assertEqual((self.lamp.files, [c for c in self.lamp.calls if c[0] == "post"]), ({}, [("post", {"rmcpal": 0})] * 3))

    def test_a_delete_the_lamp_keeps_losing_fails(self):
        self.with_palettes(0)
        self.lamp.lost, self.args.remove_palette = 3, [0]
        with self.assertRaisesRegex(SystemExit, "/palette0.json: still on the lamp after 3 removals"):
            wledlab._cmd_install(self.args)

    def test_a_lamp_whose_list_does_not_follow_fails(self):
        # What a delete through /edit does (wled_server.cpp): the file goes, the palette list stays until a reboot.
        self.with_palettes(0)
        self.lamp.keeps_list, self.args.remove_palette = True, [0]
        with self.assertRaisesRegex(SystemExit, "still counts 1 after its highest slot 0 went"):
            wledlab._cmd_install(self.args)

    def test_an_answer_that_is_neither_there_nor_gone_stops_the_removal(self):
        self.with_palettes(0)
        self.args.remove_palette = [0]
        with patch.object(wledlab, "settings_request", lambda host, path, fields=None: 401), self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.calls, [])

    def test_a_changed_file_a_preset_shows_is_recalled_again(self):
        wledlab._cmd_install(self.args)
        self.lamp.files["/squid-eyes.gif"] = b"an older loop"
        self.lamp.calls = []
        wledlab._cmd_install(self.args)
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"], ["/squid-eyes.gif"])
        self.assertIn(("post", {"on": True, "ps": 4}), self.lamp.calls)

    def test_without_restore_the_last_preset_stays(self):
        self.args.restore = False
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.state["seg"][0]["n"], "squid-eyes.gif")


if __name__ == "__main__":
    unittest.main()
