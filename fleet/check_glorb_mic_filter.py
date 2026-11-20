"""Check the configured GLORB filter against measurements from the factory application."""

import argparse
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
VECTORS = (
    (80, 8192, (1452.9989014, 1432.9643555, 1432.9428711, 1433.0407715)),
    (631.25, 257, (67.0615921, 62.9291687, 62.9604797, 62.9506149)),
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
        for hz, amplitude, expected in VECTORS:
            pcm = [round(amplitude * math.sin(2 * math.pi * hz * i / 22050)) for i in range(2048)]
            result = subprocess.check_output([binary], input=struct.pack("<2048h", *pcm))
            if len(result) != 8192:
                raise ValueError("Expected four complete blocks")
            samples = struct.unpack("<2048f", result)
            peaks = [max(abs(v) for v in samples[i:i + 512]) for i in range(0, 2048, 512)]
            # Native and Xtensa compilers round intermediate floating-point operations differently.
            for block, (actual, reference) in enumerate(zip(peaks, expected), start=1):
                if not math.isclose(actual, reference, rel_tol=1e-6, abs_tol=1e-5):
                    raise ValueError(f"{hz} Hz block {block}: expected peak {reference}, measured {actual}")
            print(f"{hz} Hz: factory filter response verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compile_database", type=Path)
    verify(parser.parse_args().compile_database)
