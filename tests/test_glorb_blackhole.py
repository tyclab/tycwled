"""Black Hole's palette call follows the original instructions.

The original passes mcol 0 to the Segment palette wrapper (0x420431d9 copies a
register zeroed at 0x420431c9 into a14) and never reads check1. mcol only
matters with palette 0, where it selects the segment colour.
"""
import unittest

from test_glorb_palette import SOURCE, function


class BlackHole(unittest.TestCase):
    def test_palette_call_passes_mcol_zero(self):
        body = function(SOURCE.read_text(), "glorb_mode_blackhole")
        self.assertIn("glorb_color_from_palette(i * 63, false, PALETTE_SOLID_WRAP, 0)", body)

    def test_check1_is_not_read(self):
        body = function(SOURCE.read_text(), "glorb_mode_blackhole")
        self.assertNotIn("check1", body)


if __name__ == "__main__":
    unittest.main()
