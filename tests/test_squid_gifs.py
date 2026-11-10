"""The committed squid GIFs: the size each lamp's Image effect plays unscaled, animated, and looping."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wledlab  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# file -> (width, height, frames): the curtain's ledmap, the couch strip, a GLORB's raster, the Moon's matrix
GIFS = {
    "curtain/squid-breathing.gif": (68, 42, 200), "curtain/squid-ink.gif": (68, 42, 120),
    "curtain/squid-deepsea.gif": (68, 42, 200), "curtain/squid-eyes.gif": (68, 42, 200),
    "curtain/squid-skin.gif": (68, 42, 120), "fleet/squid/squid-arms-300x1.gif": (300, 1, 40),
    "fleet/squid/squid-arms-20x6.gif": (20, 6, 40), "fleet/squid/squid-arms-8x8.gif": (8, 8, 40),
}


class SquidGifs(unittest.TestCase):
    def test_every_loop_has_its_lamps_size_and_frame_count(self):
        for path, (width, height, frames) in GIFS.items():
            with self.subTest(path=path), open(os.path.join(ROOT, path), "rb") as f:
                raw = f.read()
                self.assertEqual((raw[:6], int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")),
                                 (b"GIF89a", width, height))
                self.assertEqual(wledlab.gif_frames(raw), frames)
                self.assertIn(b"NETSCAPE2.0\x03\x01\x00\x00\x00", raw, "loops forever")

    def test_no_other_squid_gif_is_committed_unlisted(self):
        found = {os.path.relpath(os.path.join(folder, name), ROOT)
                 for folder in (os.path.join(ROOT, "curtain"), os.path.join(ROOT, "fleet", "squid"))
                 for name in os.listdir(folder) if name.startswith("squid-") and name.endswith(".gif")}
        self.assertEqual(found, set(GIFS))


if __name__ == "__main__":
    unittest.main()
