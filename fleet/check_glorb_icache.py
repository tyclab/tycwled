"""Check that a built GLORB image is laid out for the 32 KB instruction cache it switches to.

glorb_fx gives the ESP32-S3 its second instruction-cache bank at start. That bank's RAM
(0x40374000-0x40378000) must then hold no code and must be reserved from the heap, and the switch itself
must lie in RAM; an image that breaks one of them overwrites its own code or heap or stops at start. The
image is checked whole (every segment, checksum, SHA-256) and for where its RAM code starts. The heap
record and the switch need symbols: they are checked on the ELF the image names as its source, with the
checks the build runs after linking (glorb_fx/icache_32kb.py).
"""
import argparse
import functools
import hashlib
import importlib.util
import operator
from pathlib import Path
import struct

BANK = (0x40374000, 0x40378000)
RAM_CODE = (0x40370000, 0x403E0000)
ELF_SHA256 = slice(0xB0, 0xD0)  # app_elf_sha256 of the application description at the first segment's start
LAYOUT = Path(__file__).resolve().parents[1] / "glorb/usermod/glorb_fx/icache_32kb.py"


def segments(image):
    """Load address and bytes of each segment of an ESP32 application image that is whole."""
    if len(image) < 24 or image[0] != 0xE9:
        raise ValueError("not an ESP32 application image")
    offset, checksum, loaded = 24, 0xEF, []
    for _ in range(image[1]):
        if offset + 8 > len(image):
            raise ValueError(f"the image ends at {len(image)} bytes, inside a segment header")
        address, length = struct.unpack_from("<II", image, offset)
        data = image[offset + 8:offset + 8 + length]
        if len(data) != length:
            raise ValueError(f"the image ends inside the segment at {address:#x}: {len(data)} of {length} bytes")
        checksum = functools.reduce(operator.xor, data, checksum)
        loaded.append((address, data))
        offset += 8 + length
    end = (offset + 16) & ~15  # padded to 16 bytes, the checksum in the last one
    if len(image) < end or image[end - 1] != checksum:
        raise ValueError("the image's checksum does not match its segments")
    if not image[23] or hashlib.sha256(image[:end]).digest() != image[end:end + 32]:
        raise ValueError("the image's SHA-256 is missing or does not match its content")
    return loaded


def check(image, elf):
    code = [address for address, _ in segments(image) if RAM_CODE[0] <= address < RAM_CODE[1]]
    if not code:
        raise ValueError("no RAM code segment in the image")
    for address in code:
        if address < BANK[1]:
            raise ValueError(f"RAM code at {address:#x} lies in the instruction cache's RAM (below {BANK[1]:#x}); "
                             "the build did not use glorb_fx/icache_32kb.py")
    if image[ELF_SHA256] != hashlib.sha256(elf).digest():
        raise ValueError("the ELF belongs to another build than the image")
    spec = importlib.util.spec_from_file_location("icache_32kb", LAYOUT)
    layout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(layout)
    _, switch = layout.check_elf(elf)
    return min(code), switch


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="fleet_glorb.bin")
    parser.add_argument("elf", type=Path, help="fleet_glorb.elf, the ELF the image was made from")
    arguments = parser.parse_args()
    start, switch = check(arguments.image.read_bytes(), arguments.elf.read_bytes())
    print(f"RAM code starts at {start:#x}, the cache switch is at {switch:#x}; {BANK[0]:#x}-{BANK[1]:#x} is "
          "reserved from the heap for the second cache bank")
