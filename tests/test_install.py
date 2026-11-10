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
    """A controller that stores uploads, recalls presets and plays a GIF only when it holds the file."""

    def __init__(self):
        self.files, self.calls, self.frozen, self.deaf = {}, [], False, False
        self.state = {"on": True, "bri": 100, "seg": [segment(191)]}

    def upload(self, host, name, path, timeout=30):
        self.calls.append(("upload", name))
        self.files[name] = open(path, "rb").read()
        return "ok"

    def readback(self, host, name, timeout=10):
        return self.files.get(name, b"")

    def get(self, host, path):
        if path == "/json/info":
            return {"ver": "16.0.1", "leds": {}}
        state = copy.deepcopy(self.state)
        state["seg"] = [{k: v for k, v in seg.items() if k != "n" or v} for seg in state["seg"]]
        return state

    def post(self, host, path, body):
        self.calls.append(("post", copy.deepcopy(body)))
        if "ps" in body:
            self.state.update(on=True, seg=copy.deepcopy(json.loads(self.files["/presets.json"])[str(body["ps"])]["seg"]))
        elif "seg" in body and not self.deaf:
            self.state.update(on=body["on"], bri=body["bri"], seg=copy.deepcopy(body["seg"]))

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
        for name in ("upload", "readback", "get", "post", "live"):
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
        self.assertEqual(self.lamp.state, before)
        self.assertEqual(self.lamp.calls[-1][1]["transition"], 0)

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

    def test_a_palette_file_must_be_counted_by_the_lamp(self):
        palette = os.path.join(ROOT, "fleet", "tycstation", "palette0.json")
        self.args.presets, self.args.restore, self.args.file = None, False, [palette]
        info = {"ver": "16.0.1", "leds": {}, "cpalcount": 0}
        with patch.object(wledlab, "get", lambda host, path: info if path == "/json/info" else {"seg": []}), \
                self.assertRaisesRegex(SystemExit, "uploaded slot 0"):
            wledlab._cmd_install(self.args)
        info["cpalcount"] = 1
        with patch.object(wledlab, "get", lambda host, path: info if path == "/json/info" else {"seg": []}):
            wledlab._cmd_install(self.args)
        self.assertEqual(self.lamp.files["/palette0.json"], open(palette, "rb").read())

    def test_files_and_presets_already_on_the_lamp_are_not_sent_or_recalled(self):
        wledlab._cmd_install(self.args)
        before, self.lamp.calls = copy.deepcopy(self.lamp.state), []
        palette = os.path.join(ROOT, "fleet", "tycstation", "palette0.json")
        self.args.file = self.args.file + [palette]
        info = {"ver": "16.0.1", "leds": {}, "cpalcount": 1}
        with patch.object(wledlab, "get", lambda host, path: info if path == "/json/info" else self.lamp.get(host, path)):
            wledlab._cmd_install(self.args)
        # Only the new palette goes up; no preset is recalled, so the look is not touched.
        self.assertEqual([c[1] for c in self.lamp.calls if c[0] == "upload"], ["/palette0.json"])
        self.assertEqual([c for c in self.lamp.calls if c[0] == "post"], [])
        self.assertEqual(self.lamp.state, before)

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
