"""Structural-gate math against synthetic frames with known properties.

The 2026-08-27 review found every capture-analysis function untested; these are the
gate's pure functions, checked against signals whose statistics are known in closed form.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wledlab  # noqa: E402


def frames_from_grid(rows, n_frames=30, dt=0.1):
    """Constant frames: one hex cell list repeated with increasing timestamps."""
    leds = ["%02x%02x%02x" % (v, v, v) for v in rows]
    return [(round(k * dt, 3), list(leds)) for k in range(n_frames)]


class CircEmd(unittest.TestCase):
    def test_identical_is_zero(self):
        p = [0.5, 0.25, 0.25] + [0] * 9
        self.assertEqual(wledlab.circ_emd(p, p), 0)

    def test_length_mismatch_asserts(self):
        with self.assertRaises(AssertionError):
            wledlab.circ_emd([1.0, 0.0], [0.0] * 12)

    def test_adjacent_shift_costs_one_bin(self):
        # all mass moving one bin over = 1 bin x 1 mass
        p = [1.0] + [0] * 11
        q = [0, 1.0] + [0] * 10
        self.assertAlmostEqual(wledlab.circ_emd(p, q), 1.0)

    def test_wraparound_is_short_way(self):
        # bin 11 -> bin 0 is one step across the wrap, not eleven around
        p = [0] * 11 + [1.0]
        q = [1.0] + [0] * 11
        self.assertAlmostEqual(wledlab.circ_emd(p, q), 1.0)

    def test_red_split_is_cheap(self):
        # the review's failure case: one colour split across bins 0/11 vs concentrated
        p = [0.5] + [0] * 10 + [0.5]
        q = [1.0] + [0] * 11
        self.assertAlmostEqual(wledlab.circ_emd(p, q), 0.5)
        # plain per-bin L1/2 would charge the same as a real hue change; EMD must not
        far = [0] * 6 + [1.0] + [0] * 5
        self.assertGreater(wledlab.circ_emd(p, far), 5 * wledlab.circ_emd(p, q))


class StructuralStats(unittest.TestCase):
    def test_uniform_bright_grid(self):
        fr = frames_from_grid([200] * 8)
        s = wledlab.structural_stats(fr, step=1)
        self.assertAlmostEqual(s["mean"], 200 / 255, places=2)
        self.assertEqual(s["tstd"], 0)
        self.assertEqual(s["sstd"], 0)
        self.assertEqual(s["lit"], 8)
        self.assertAlmostEqual(sum(s["vhist"]), 1.0)
        self.assertAlmostEqual(s["vhist"][7], 1.0)  # 200/255 = 0.784 -> bin 7

    def test_dark_cells_excluded_like_ledmap_holes(self):
        # cells that never exceed 0.05 (holes) must not count as "black pixels"
        fr = frames_from_grid([0, 0, 0, 0, 255, 255, 255, 255])
        s = wledlab.structural_stats(fr, step=1)
        self.assertEqual(s["lit"], 4)
        self.assertEqual(s["vhist"][0], 0)
        self.assertAlmostEqual(s["vhist"][9], 1.0)

    def test_bimodal_vs_flat_histogram_distance(self):
        # the preset-14 signature: bimodal black/full vs everything mid-grey
        bimodal = frames_from_grid([13, 13, 13, 255, 255, 255, 128, 128])
        flat = frames_from_grid([128] * 8)
        a = wledlab.structural_stats(bimodal, step=1)
        b = wledlab.structural_stats(flat, step=1)
        vd = sum(abs(x - y) for x, y in zip(a["vhist"], b["vhist"])) / 2
        self.assertGreater(vd, 0.7)
        self.assertGreater(a["sstd"], 0.3)
        self.assertEqual(b["sstd"], 0)


class NullCases(unittest.TestCase):
    def test_all_dark_capture_zeroed_not_crash(self):
        s = wledlab.structural_stats(frames_from_grid([0, 0, 0, 0]), step=1)
        self.assertEqual(s["lit"], 0)
        self.assertEqual(s["peak"], 0.0)

    def test_gate_scores_dark_target_no_crash(self):
        ref = frames_from_grid([200] * 6, n_frames=20)
        tgt = frames_from_grid([0] * 6, n_frames=20)
        self.assertEqual(wledlab.gate_scores(ref, tgt)["peak_r"], 0.0)
        self.assertIsNone(wledlab.gate_scores(tgt, ref)["peak_r"])

    def test_hue_shares_sums_to_one(self):
        fr = frames_from_grid([200, 50, 250, 90], n_frames=10)
        self.assertAlmostEqual(sum(wledlab.hue_shares(fr, step=1)), 1.0)


class LoadCapture(unittest.TestCase):
    def test_all_three_formats(self):
        import json
        import tempfile
        fr = frames_from_grid([10, 250], n_frames=2)
        # meta must survive load_capture: rescore reads meta["window"] to apply the
        # same coverage/gap health refusal the live gate applies (dropping it made
        # those checks dead code and let rescore bless a gapped capture)
        for payload, keys in ((fr, [""]), ({"meta": {}, "frames": fr}, [""]),
                              ({"meta": {"window": 9}, "ref": fr, "tgt": fr}, ["meta", "ref", "tgt"])):
            import os
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(payload, f)
            try:
                got = wledlab.load_capture(f.name)
                self.assertEqual(sorted(got), sorted(keys))
                for k, v in got.items():
                    if k == "meta":
                        self.assertEqual(v, {"window": 9})
                    else:
                        self.assertEqual(len(v), 2)
            finally:
                os.unlink(f.name)


class CaptureHealth(unittest.TestCase):
    def test_clean_capture(self):
        fr = frames_from_grid([100] * 4, n_frames=101, dt=0.1)
        h = wledlab.capture_health(fr, seconds=10)
        self.assertEqual(h["frames"], 101)
        self.assertAlmostEqual(h["hz"], 10.0, places=1)
        self.assertGreaterEqual(h["coverage"], 0.99)
        self.assertLessEqual(h["max_gap"], 0.101)

    def test_gap_detected(self):
        fr = frames_from_grid([100] * 4, n_frames=50, dt=0.1)
        fr += [(t + 8.0, f) for t, f in frames_from_grid([100] * 4, n_frames=50, dt=0.1)]
        h = wledlab.capture_health(fr, seconds=10)
        self.assertGreater(h["max_gap"], 2.0)

    def test_short_capture_low_coverage(self):
        fr = frames_from_grid([100] * 4, n_frames=30, dt=0.1)  # 3 s of a 10 s window
        h = wledlab.capture_health(fr, seconds=10)
        self.assertLess(h["coverage"], 0.5)

    def test_degenerate(self):
        self.assertEqual(wledlab.capture_health([], seconds=5)["frames"], 0)
        self.assertEqual(wledlab.capture_health(frames_from_grid([1], n_frames=1), 5)["hz"], 0.0)


if __name__ == "__main__":
    unittest.main()
