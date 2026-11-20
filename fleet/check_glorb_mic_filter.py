"""Check the configured GLORB filter against measurements from the factory application."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import struct
import subprocess
import tempfile


def filter_source(database):
    entries = json.loads(database.read_text())
    entry, = [row for row in entries if Path(row["file"]).name == "audio_reactive.cpp"]
    command = shlex.split(entry["command"])
    output = command.index("-o")
    del command[output:output + 2]
    command[command.index("-c")] = "-E"
    source = subprocess.check_output([*command, "-P"], cwd=entry["directory"], text=True)
    signature = re.search(r"static void runMicFilter\([^;{}]*\)\s*\{", source)
    if not signature or "using FFTsampleType = float;" not in source:
        raise ValueError("Expected an active floating-point AudioReactive microphone filter")
    depth = 1
    for end in range(signature.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[signature.start():end + 1]
    raise ValueError("Incomplete microphone filter")


# The factory GLORB.1.3 application (SHA-256 ba2decaa…) was run on a virtual
# ESP32-S3 with these authored signed PCM samples at the driver's read boundary.
# Each check starts from reset filter history, then feeds four consecutive blocks.
# Each row gives Hz, PCM amplitude, quantization step in filtered counts, then
# the peak and SHA-256 of all 512 ordered, signed samples in each block.
# At these steps every factory sample is farther from a rounding boundary
# than the maximum measured host-to-Xtensa error for its tone.
VECTORS = (
    (80, 8192, 2.0, (
        (1452.9989014, "cb054139405d3c56d7205b736823c4ebc70e386787c7f771a65089f561566ae9"),
        (1432.9643555, "dcbc05dac0db9ef8a4d8d8751ae2fb9cc4b22469ba3959652f6e219bf04198da"),
        (1432.9428711, "bbe0a20c554f984d4dfc3c78aa862ff49823700fe0352120adb03ade76da7f75"),
        (1433.0407715, "2d8527ce2b17eebb6f9730fee53c2eccc72a5600eeadea0c2c4ee51bb62c588e"),
    )),
    (631.25, 257, 0.5, (
        (67.0615921, "351369d8e835297f6b792e3dd17d218023da14bfcff61f9ffdaa386f53c0f742"),
        (62.9291687, "ac0f5d34142d1f087b6d2519d84e8f2a8977e8354a97124c15b901b278a0438a"),
        (62.9604797, "b81e0dfb098d1efc8533690cbc4a98bd7cb5ad82674373857a8226300997b237"),
        (62.9506149, "b4ec00706fcb740c866480f1590c68f0e32850b7705a1dde3fe2b9e891b6188e"),
    )),
)
DRIVER = r"""
int main() {
    int16_t pcm[512];
    float block[512];
    while (std::fread(pcm, sizeof(int16_t), 512, stdin) == 512) {
        for (int i = 0; i < 512; ++i) block[i] = pcm[i] * 0.25f;
        runMicFilter(512, block);
        if (std::fwrite(block, sizeof(float), 512, stdout) != 512) return 1;
    }
    return std::ferror(stdin) ? 1 : 0;
}
"""


def verify(database):
    source = filter_source(database)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        cpp = path / "filter.cpp"
        cpp.write_text("#include <cstdint>\n#include <cstdio>\nusing FFTsampleType = float;\n" + source + DRIVER)
        binary = path / "filter"
        subprocess.run(["c++", "-std=c++17", "-O2", "-ffp-contract=off", cpp, "-o", binary], check=True)
        for hz, amplitude, step, expected in VECTORS:
            pcm = [round(amplitude * math.sin(2 * math.pi * hz * i / 22050)) for i in range(2048)]
            result = subprocess.check_output([binary], input=struct.pack("<2048h", *pcm))
            if len(result) != 8192:
                raise ValueError("Expected four complete blocks")
            samples = struct.unpack("<2048f", result)
            for index, (reference_peak, digest) in enumerate(expected):
                block = samples[512 * index:512 * (index + 1)]
                peak = max(abs(value) for value in block)
                if not math.isclose(peak, reference_peak, rel_tol=1e-6, abs_tol=1e-5):
                    raise ValueError(f"{hz} Hz block {index + 1}: expected peak {reference_peak}, measured {peak}")
                signed = struct.pack("<512h", *(round(value / step) for value in block))
                if hashlib.sha256(signed).hexdigest() != digest:
                    raise ValueError(f"{hz} Hz block {index + 1}: signed waveform differs from factory")
            print(f"{hz} Hz: factory filter response verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compile_database", type=Path)
    verify(parser.parse_args().compile_database)
