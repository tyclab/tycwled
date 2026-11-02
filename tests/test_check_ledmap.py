import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wledlab  # noqa: E402


class CheckLedmapTests(unittest.TestCase):
    def run_check(self, powers=(100, 100), raw=b'{"map":[0]}', post_error=None):
        with patch.object(sys, "argv", ["wledlab", "check-ledmap", "--ref", "reference",
                                      "--target", "target", "--restore-preset", "4"]), \
                patch.object(wledlab, "white_estimate", side_effect=powers), \
                patch.object(wledlab, "readback", return_value=raw), \
                patch.object(wledlab, "post", side_effect=post_error) as post, \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                wledlab.main()
                status = 0
            except SystemExit as exc:
                status = exc.code
            except OSError:
                status = 1
        self.assertEqual(post.call_args_list, [
            call("reference", "/json/state", {"on": True, "bri": 255, "ps": 4}),
            call("target", "/json/state", {"on": True, "bri": 255, "ps": 4}),
        ])
        return status

    def test_matching_current_and_exact_map_succeed(self):
        self.assertEqual(self.run_check(), 0)

    def test_current_mismatch_and_unmeasurable_reference_fail(self):
        for powers in ((100, 150), (0, 100)):
            with self.subTest(powers=powers):
                self.assertEqual(self.run_check(powers=powers), 1)

    def test_map_with_wrong_bytes_fails(self):
        self.assertEqual(self.run_check(raw=b'{"map": [0]}'), 1)

    def test_measurement_failure_still_restores_both_lamps(self):
        self.assertEqual(self.run_check(powers=OSError("offline")), 1)

    def test_first_restore_failure_still_restores_target(self):
        self.assertEqual(self.run_check(post_error=[OSError("offline"), None]), 1)
