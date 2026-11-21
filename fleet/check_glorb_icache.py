"""Check that a built GLORB image is laid out for the 32 KB instruction cache it switches to.

glorb_fx gives the ESP32-S3 its second instruction-cache bank at start. That bank's RAM
(0x40374000-0x40378000) must then hold no code and must be reserved from the heap; an image that breaks
either would overwrite its own code or heap on the lamp. That the switch function itself lies in RAM is
checked on the ELF at build time (glorb_fx/icache_32kb.py); an application image carries no symbols.
"""
import argparse
from pathlib import Path
import struct

BANK = (0x40374000, 0x40378000)
RAM_CODE = (0x40370000, 0x403E0000)


def segments(image):
    if len(image) < 24 or image[0] != 0xE9:
        raise ValueError("not an ESP32 application image")
    offset = 24
    for _ in range(image[1]):
        address, length = struct.unpack_from("<II", image, offset)
        yield address, image[offset + 8:offset + 8 + length]
        offset += 8 + length


def check(image):
    loaded = list(segments(image))
    code = [address for address, _ in loaded if RAM_CODE[0] <= address < RAM_CODE[1]]
    if not code:
        raise ValueError("no RAM code segment in the image")
    for address in code:
        if address < BANK[1]:
            raise ValueError(f"RAM code at {address:#x} lies in the instruction cache's RAM (below {BANK[1]:#x}); "
                             "the build did not use glorb_fx/icache_32kb.py")
    record = struct.pack("<II", *BANK)
    if not any(record in data for _, data in loaded):
        raise ValueError(f"the image does not reserve {BANK[0]:#x}-{BANK[1]:#x} from the heap")
    return min(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="fleet_glorb.bin")
    start = check(parser.parse_args().image.read_bytes())
    print(f"RAM code starts at {start:#x}; {BANK[0]:#x}-{BANK[1]:#x} is reserved for the second cache bank")
