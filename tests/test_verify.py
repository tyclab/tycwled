"""verify refuses a run that cannot measure before it touches either lamp."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wledlab  # noqa: E402


class VerifyRefusals(unittest.TestCase):
    def refused(self, presets, samples=200, interval=0.5):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text(json.dumps(presets))
            args = SimpleNamespace(presets_file=str(path), samples=samples, interval=interval,
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

    def test_nonpositive_window(self):
        for samples, interval in ((0, 0.5), (-1, 0.5), (200, 0), (200, -0.5)):
            with self.subTest(samples=samples, interval=interval):
                self.assertIn("must be positive", self.refused({"1": {"n": "solid"}}, samples, interval))


if __name__ == "__main__":
    unittest.main()
