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
    writing a segment with an effect ends a running playlist."""

    def __init__(self):
        self.files, self.calls, self.frozen, self.deaf, self.stuck, self.drops, self.mute = {}, [], False, False, False, 0, 0
        # Custom palettes as loadCustomPalettes (colors.cpp) left them, and how many deletes the filesystem loses.
        self.palettes, self.lost, self.keeps_list = 0, 0, False
        self.state = {"on": True, "bri": 100, "ps": -1, "pl": -1, "transition": 7, "seg": [segment(191)]}

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
        return 200 if path in self.files else 404

    def get(self, host, path):
        if path == "/json/info":
            return {"ver": "16.0.1", "leds": {}, "cpalcount": self.palettes}
        state = copy.deepcopy(self.state)
        state["seg"] = [{k: v for k, v in seg.items() if k != "n" or v} for seg in state["seg"]]
        return state

    def post(self, host, path, body):
        self.calls.append(("post", copy.deepcopy(body)))
        if "rmcpal" in body:
            # json.cpp deserializeState: the file is removed if it is there, the result is not looked at, and the
            # custom palettes are loaded again. Nothing else of the state changes.
            if self.lost:
                self.lost -= 1
            else:
                self.files.pop(f"/palette{body['rmcpal']}.json", None)
            if not self.keeps_list:
                self.load_palettes()
        elif "ps" in body:
            presets = json.loads(self.files["/presets.json"])
            preset, playlist = presets[str(body["ps"])], -1
            self.state.update(on=body.get("on", self.state["on"]), bri=body.get("bri", self.state["bri"]))
            if "playlist" in preset and not self.stuck:
                playlist, preset = body["ps"], presets[str(preset["playlist"]["ps"][0])]
            if "seg" in preset:
                self.state.update(on=True, ps=body["ps"] if playlist < 0 else presets[str(playlist)]["playlist"]["ps"][0],
                                  seg=copy.deepcopy(preset["seg"]))
            self.state["pl"] = playlist
        elif "seg" in body and not self.deaf:
            if any("fx" in seg for seg in body["seg"]):
                self.state["pl"] = -1
            self.state.update(on=body["on"], bri=body["bri"], ps=body.get("pd", -1), seg=copy.deepcopy(body["seg"]),
                              transition=body.get("transition", self.state["transition"]))

    def live(self, host, seconds):
        name = "/" + self.state["seg"][0].get("n", "")
        frames = 1 if self.frozen else wledlab.gif_frames(self.files.get(name, b""))
        return [(i / 10, [f"{i % max(frames, 1):06x}"]) for i in range(10)]


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

    def test_presets_go_up_compact_whatever_the_file_looks_like(self):
        presets = json.load(open(self.presets))
        with open(self.presets, "w") as f:
            json.dump(presets, f, indent=2)
        wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.files["/presets.json"], json.dumps(presets, separators=(",", ":")).encode())

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
        # A playlist holds no segments (the Exoy controller's presets 20 to 22); left running it would switch a lamp
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
