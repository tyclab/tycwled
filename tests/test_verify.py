"""Verify refusals, public acceptance summaries and private capture diagnostics."""
from contextlib import redirect_stderr, redirect_stdout
import io
import itertools
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_private_lamp_data  # noqa: E402
import wledlab  # noqa: E402


class VerifyRefusals(unittest.TestCase):
    def refused(self, presets):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text(json.dumps(presets))
            args = SimpleNamespace(presets_file=str(path), samples=200, interval=0.5,
                                   ref="reference", target="target", restore_preset=4)
            with patch.object(wledlab, "post") as post, patch.object(wledlab, "get") as get, \
                    patch.object(wledlab, "lamp_meta") as meta, \
                    self.assertRaises(SystemExit) as result:
                wledlab.cmd_verify(args)
        for device_io in (post, get, meta):
            device_io.assert_not_called()
        return str(result.exception.code)

    def test_empty_or_all_skipped_presets(self):
        for presets in ({}, {"0": {}, "1": None}):
            with self.subTest(presets=presets):
                self.assertIn("no testable preset", self.refused(presets))


class VerifySummary(unittest.TestCase):
    def run_verify(self, presets):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text(json.dumps({k: {"n": "private-preset-name"} for k in presets}))
            captures = Path(directory) / "private-capture-path"
            ref, target = "private-ref.invalid", "private-target.invalid"
            bssid = ":".join(["02"] * 6)
            active = {}
            frames = [(i / 10, ["ff0000", "003300"] if i < 5 else ["003300", "ff0000"])
                      for i in range(11)]

            def post(host, route, body):
                active[host] = body["ps"]

            def get(host, route):
                preset = active.get(host)
                if route == "/json/state":
                    if preset == 3:
                        raise OSError("private-diagnostic")
                    return {"ps": 0 if preset == 2 and host == target else preset}
                return {"ver": "16.0.1-private-build", "wifi": {"bssid": bssid},
                        "leds": {"pwr": 800 if preset == 4 and host == target else 400,
                                 "fps": 42, "maxpwr": "private-invalid-number"}}

            args = ["wledlab", "--width", "2", "--height", "1", "verify", "--ref", ref,
                    "--target", target, "--presets-file", str(path), "--samples", "1",
                    "--interval", "1", "--save-captures", str(captures)]
            out, err = io.StringIO(), io.StringIO()
            with patch.object(sys, "argv", args), patch.object(wledlab, "get", get), \
                    patch.object(wledlab, "post", post), patch.object(wledlab.time, "sleep"), \
                    patch.object(wledlab.time, "time", side_effect=itertools.count(0, 0.6)), \
                    patch.object(wledlab, "live_ws", side_effect=OSError("private-stream-error")), \
                    patch.object(wledlab, "live_http", return_value=frames), \
                    redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as result:
                wledlab.main()
            recording = wledlab.load_capture(captures / "verify-p1.json")
            saved = (captures / "verify-p1.json").read_bytes()
            for lamp in ("ref", "tgt"):
                self.assertEqual(sorted(recording["meta"][lamp]), ["cpalcount", "fps", "maxpwr", "state", "ver"])
            for private in (ref, target, bssid):
                self.assertNotIn(private.encode(), saved)
            self.assertEqual(check_private_lamp_data.findings("saved.json", saved), ["a raw lamp recording"])
            self.assertEqual(len(recording["ref"]), 11)
            self.assertNotIn("private", out.getvalue())
            self.assertIn("private-stream-error", err.getvalue())
            self.assertIn("HTTP polling fallback", out.getvalue())
            self.assertIn("ref: version 16.0.1 fps 42", out.getvalue())
            self.assertIn("structural tolerances vhist 0.25", out.getvalue())
            self.assertIn("400 mA  target   400 mA  ratio 1.000", out.getvalue())
            return result.exception.code, out.getvalue(), err.getvalue()

    def test_success(self):
        code, summary, _ = self.run_verify([1])
        self.assertEqual(code, 0)
        self.assertIn("1/1 presets passed, 1/1 measured", summary)
        self.assertTrue(summary.rstrip().endswith("verify: PASS"))

    def test_partial_and_scored_failures(self):
        code, summary, diagnostics = self.run_verify([1, 2, 3, 4])
        self.assertEqual(code, 1)
        self.assertIn("preset  2 FAIL (preset did not apply on target)", summary)
        self.assertIn("preset  3 FAIL (measurement error)", summary)
        self.assertIn("private-diagnostic", diagnostics)
        self.assertIn("FAIL current", summary)
        self.assertIn("1/4 presets passed, 2/4 measured", summary)
        self.assertIn("verify: FAIL", summary)


if __name__ == "__main__":
    unittest.main()
