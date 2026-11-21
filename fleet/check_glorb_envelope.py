"""Run the configured GLORB PDM envelope clock at different main-loop cadences."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from check_glorb_mic_filter import configured_source, function

# The factory image with sound transmission off, as on the installed lamps, crosses Running's
# three-to-two-step threshold as a 429 us microphone clock does (about 2,331 updates/s). 467 us matched
# the factory while it transmitted its audio values, which slows its main loop.
PERIOD_US = 429


def firmware_clock(source):
    dispatch = re.search(r"if\s*\(dmType == 5\)\s*\{\s*updatePdmEnvelope\(\);", source)
    if not dispatch:
        raise ValueError("The GLORB local PDM path does not use the envelope clock")
    constants = []
    for name in ("samplesFFT", "SAMPLE_RATE"):
        match = re.search(r"constexpr \w+ " + name + r" = (\d+);", source)
        if not match:
            raise ValueError(f"Missing configured {name}")
        constants.append(f"constexpr uint32_t {name} = {match[1]};")
    tables = re.findall(r"^const (?:float|double) agc\w+\[\d+\] = \{[^}]+\};", source, re.M)
    # ESP32 unsigned long is 32 bits, including the PI controller's persistent clock.
    agc = function(source, "void agcAvg").replace("unsigned long", "uint32_t")
    clock = function(source, "void updatePdmEnvelope")
    period = re.search(r"constexpr uint32_t periodUs = (\d+);", clock)
    if not period or int(period[1]) != PERIOD_US:
        raise ValueError(f"The GLORB PDM envelope period is not the calibrated {PERIOD_US} us")
    return "\n".join([*constants, "namespace pi {", *tables, agc, "}", clock])


DRIVER = r"""
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdlib>

uint64_t nowUs, startUs;
uint32_t samples, lastAgcMs;
int64_t esp_timer_get_time() { return static_cast<int64_t>(nowUs); }
uint32_t millis() { return static_cast<uint32_t>(nowUs / 1000); }
namespace pi {
    int soundAgc = 1, last_soundAgc = 1, soundSquelch = 0;
    float sampleReal = 0, multAgc = 1, sampleAgc = 0;
    int16_t rawSampleAgc = 0;
    double sampleMax = 0, control_integrated = 1;
}
void getSample() { ++samples; }
bool checkSequence = true;
void agcAvg(uint32_t when, bool scheduled) {
    assert(scheduled);
    if (checkSequence) {
        const uint32_t expectedMs = (startUs + uint64_t(samples - 1) * PERIOD_US) / 1000;
        assert(when == expectedMs);
    }
    lastAgcMs = when;
}
"""

CHECK = r"""
void expectPiUpdate(uint32_t stamp, bool scheduled, bool expected) {
    // With a quiet input each PI update decays its nonzero integrator.
    const double before = pi::control_integrated;
    if (scheduled) pi::agcAvg(stamp, true);
    else pi::agcAvg(stamp);
    assert((pi::control_integrated != before) == expected);
}

int main(int argc, char **argv) {
    nowUs = 1008000;
    expectPiUpdate(1000, false, true);
    expectPiUpdate(1002, false, false);
    expectPiUpdate(0, false, true);     // Legacy zero uses the wall clock at 1008 ms.
    nowUs = 1011000;
    expectPiUpdate(2000, false, true);  // Legacy future stamp uses 1011 ms.
    nowUs = 1030000;                   // The task resumes late for the scheduled samples.
    expectPiUpdate(1012, true, false);
    expectPiUpdate(1014, true, true);
    nowUs = ((uint64_t(1) << 32) + 20) * 1000;
    expectPiUpdate(UINT32_MAX - 5, true, true);
    expectPiUpdate(UINT32_MAX - 4, true, false);
    expectPiUpdate(UINT32_MAX - 2, true, true);
    expectPiUpdate(0, true, true);      // Scheduled zero is a real sample at rollover.
    expectPiUpdate(1, true, false);
    expectPiUpdate(3, true, true);

    startUs = std::strtoull(argv[1], nullptr, 10);
    const uint32_t loopUs = std::strtoul(argv[2], nullptr, 10);
    const uint32_t runUs = 1000000;
    for (uint32_t elapsed = 0;; elapsed = std::min(elapsed + loopUs, runUs)) {
        nowUs = startUs + elapsed;
        updatePdmEnvelope();
        // One update at t=0 and one per calibrated period, whatever the main-loop cadence.
        assert(samples == 1 + elapsed / PERIOD_US);

        if (elapsed == runUs) break;
    }
    // One retained 512-sample FFT block at 22,050 Hz spans about 23 ms.
    // When service resumes after a longer stall, only one fresh peak is available.
    checkSequence = false;
    const uint32_t priorSamples = samples;
    nowUs += 200000;
    updatePdmEnvelope();
    assert(samples == priorSamples + 1 && lastAgcMs == uint32_t(nowUs / 1000));
    nowUs += PERIOD_US - 1;
    updatePdmEnvelope();
    assert(samples == priorSamples + 1);
    ++nowUs;
    updatePdmEnvelope();
    assert(samples == priorSamples + 2);

    // A suspended local microphone can resume after the 32-bit micros counter wraps.
    const uint64_t microsecondWrap = uint64_t(1) << 32;
    for (const uint32_t offset : {100U, 10000U}) {
        const uint32_t before = samples;
        nowUs += microsecondWrap + offset;
        updatePdmEnvelope();
        assert(samples == before + 1 && lastAgcMs == uint32_t(nowUs / 1000));
    }
}
"""


def verify(database):
    clock = firmware_clock(configured_source(database))
    with tempfile.TemporaryDirectory() as directory:
        cpp = Path(directory) / "clock.cpp"
        binary = cpp.with_suffix("")
        cpp.write_text(f"#include <cstdint>\nconstexpr uint32_t PERIOD_US = {PERIOD_US};\n" + DRIVER + clock + CHECK)
        subprocess.run(["c++", "-std=c++17", "-O2", cpp, "-o", binary], check=True)
        # Include both the ESP's microsecond and millisecond counter rollover.
        for start in (0, 2**32 - 100000, (2**32 - 98) * 1000):
            for interval in (50, PERIOD_US, 340, 1550, 5000, 22000):
                subprocess.run([binary, str(start), str(interval)], check=True)
    print("GLORB PDM envelope cadence, AGC timestamps, rollover and stall recovery verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compile_database", type=Path)
    verify(parser.parse_args().compile_database)
