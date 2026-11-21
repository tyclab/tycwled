"""The GLORB build's microphone clock period and the check that guards it stay the same number."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fleet"))
import check_glorb_envelope  # noqa: E402

SOURCE = """
constexpr int samplesFFT = 512;
constexpr int SAMPLE_RATE = 22050;
void agcAvg(unsigned long the_time, bool scheduled = false) { }
void updatePdmEnvelope() {
  constexpr uint32_t periodUs = %d;
}
void loop() {
  if (dmType == 5) {
    updatePdmEnvelope();
  }
}
"""


class EnvelopePeriod(unittest.TestCase):
    def test_build_flag_equals_the_checked_period(self):
        override = (ROOT / "glorb/usermod/glorb_fx/platformio_override.ini").read_text()
        flag, = re.findall(r"-D UM_AUDIOREACTIVE_PDM_ENVELOPE_PERIOD_US=(\d+)", override)
        self.assertEqual(int(flag), check_glorb_envelope.PERIOD_US)

    def test_another_configured_period_fails_the_check(self):
        check_glorb_envelope.firmware_clock(SOURCE % check_glorb_envelope.PERIOD_US)
        with self.assertRaisesRegex(ValueError, "calibrated"):
            check_glorb_envelope.firmware_clock(SOURCE % 467)


if __name__ == "__main__":
    unittest.main()
