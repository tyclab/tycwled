"""The GLORB build runs with a 32 KB instruction cache.

Measured on an ESP32-S3 on 2026-11-21: with the SDK's 16 KB instruction cache the fleet image's main
loop runs 629-663 times a second, with 32 KB 3,010-3,055 times. The second cache bank's RAM
(0x40374000-0x40378000) holds code in the stock memory layout, so three things have to change together:
the linker script, the heap reservation and the switch.
"""
import hashlib
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USERMOD = ROOT / "glorb/usermod/glorb_fx"
sys.path.insert(0, str(ROOT / "fleet"))

STOCK_LINE = ("  iram0_0_seg (RX) : org = (0x40370000 + 0x4000), "
              "len = (((0x403CC700 - (0x40378000 - 0x3FC88000)) - 0x3FC88000) + 0x8000 - 0x4000)")
STOCK = "MEMORY\n{\n" + STOCK_LINE + "\n  dram0_0_seg (RW) : org = (0x3FC88000), len = 0x44700\n}\n"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image(segments, built_from=b""):
    """An ESP32-S3 application image (chip ID 9): header, (load address, bytes) segments, checksum and SHA-256.
    The first segment starts with the application description, which names the ELF the image was made from."""
    out = bytearray(struct.pack("<BBBBI", 0xE9, len(segments), 2, 0x3F, 0x40378000)
                    + bytes(4) + struct.pack("<H", 9) + bytes(9) + b"\x01")
    checksum = 0xEF
    for index, (address, data) in enumerate(segments):
        if index == 0:
            data = bytes(0x90) + hashlib.sha256(built_from).digest() + data
        out += struct.pack("<II", address, len(data)) + data
        for byte in data:
            checksum ^= byte
    out += bytes((15 - len(out)) % 16) + bytes([checksum])
    return bytes(out) + hashlib.sha256(out).digest()


RESERVED = struct.pack("<II", 0x40374000, 0x40378000)


def elf(symbols, data=None):
    """A 32-bit little-endian ELF: function symbols with these names and addresses, and one loaded section per
    address: bytes of data."""
    names, entries = b"\0", [bytes(16)]
    for name, value in symbols.items():
        entries.append(struct.pack("<IIIBBH", len(names), value, 0, 2, 0, 1))  # STT_FUNC
        names += name.encode() + b"\0"
    table = b"".join(entries)
    section_names = b"\0.symtab\0.strtab\0.shstrtab\0.data\0"
    body = table + names + section_names

    def section(name, kind, offset, size, link=0, entry=0, address=0, flags=0):
        return struct.pack("<10I", name, kind, flags, address, offset, size, link, 0, 1, entry)

    sections = [bytes(40), section(1, 2, 52, len(table), link=2, entry=16),
                section(9, 3, 52 + len(table), len(names)),
                section(17, 3, 52 + len(table) + len(names), len(section_names))]
    for address, content in (data or {}).items():
        sections.append(section(27, 1, 52 + len(body), len(content), address=address, flags=2))
        body += content
    header = (b"\x7fELF\x01\x01\x01" + bytes(9)
              + struct.pack("<HHIIIIIHHHHHH", 2, 94, 1, 0, 0, 52 + len(body), 0, 52, 0, 0, 40, len(sections), 3))
    return header + body + b"".join(sections)


SWITCH = "_ZL17glorb_icache_32kbv"
TABLE = {"soc_reserved_memory_region_start": 0x3C0F0100, "soc_reserved_memory_region_end": 0x3C0F0110}
LAYOUT = {"_iram_start": 0x40378000, SWITCH: 0x40378E00, **TABLE}
OTHER_RECORD = struct.pack("<II", 0x3FC88000, 0x3FC90000)
RAM = bytes(range(256)) * 15  # RAM code from 0x40378000, the switch at +0xe00 inside it


def built(table=OTHER_RECORD + RESERVED, elsewhere=b""):
    """An ELF with RAM code at 0x40378000, the SDK's table of reserved memory at 0x3c0f0100 and other read-only
    data at 0x3c0f0200."""
    return elf(LAYOUT, {0x3C0F0100: table, 0x3C0F0200: elsewhere + bytes(8), 0x40378000: RAM})


def packed(source, ram_code=0x40378000):
    """The image of a built() ELF: read-only data from 0x3c0f0020 on, flash code, RAM code."""
    script = load(USERMOD / "icache_32kb.py", "icache_32kb")
    rodata = bytearray(0x200 - 0x20 - 0xB0 + 64)
    ram = b""
    for address, data in script.loaded(source):
        if address >= 0x40000000:
            ram = data
        else:
            at = address - 0x3C0F0020 - 0xB0
            rodata[at:at + len(data)] = data
    return image([(0x3C0F0020, bytes(rodata)), (0x42000020, bytes(64)), (ram_code, ram)], source)


class LinkerScript(unittest.TestCase):
    def setUp(self):
        self.script = load(USERMOD / "icache_32kb.py", "icache_32kb")

    def test_ram_code_starts_after_both_cache_banks(self):
        patched = self.script.patch(STOCK)
        self.assertIn("iram0_0_seg (RX) : org = (0x40370000 + 0x8000), "
                      "len = (((0x403CC700 - (0x40378000 - 0x3FC88000)) - 0x3FC88000) + 0x8000 - 0x8000)", patched)
        self.assertNotIn("0x40370000 + 0x4000", patched)
        self.assertIn("dram0_0_seg (RW) : org = (0x3FC88000), len = 0x44700", patched)

    def test_a_drifted_framework_script_stops_the_build(self):
        for drifted in (STOCK.replace("0x4000)", "0x2000)"), STOCK + STOCK_LINE + "\n", "MEMORY\n{\n}\n"):
            with self.assertRaises(ValueError):
                self.script.patch(drifted)


class BuiltElf(unittest.TestCase):
    def setUp(self):
        self.script = load(USERMOD / "icache_32kb.py", "icache_32kb")

    def layout(self, symbols):
        return self.script.check_layout(symbols, symbols)

    def test_ram_code_after_both_banks_with_the_switch_in_ram_passes(self):
        self.assertEqual(self.script.check_elf(built()), (0x40378000, 0x40378E00))

    def test_ram_code_inside_the_second_bank_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "memory.ld"):
            self.layout({"_iram_start": 0x40374000, SWITCH: 0x40374E00})

    def test_a_switch_in_flash_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "flash"):
            self.layout({"_iram_start": 0x40378000, SWITCH: 0x42012340})

    def test_an_inlined_switch_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "inlined"):
            self.layout({"_iram_start": 0x40378000, "loop": 0x42001234})

    def test_a_helper_that_runs_with_the_caches_on_may_lie_in_flash(self):
        # Built without inlining (-Og), the info row's glorb_icache_bytes() is a function of its own, in flash.
        self.assertEqual(self.layout({**LAYOUT, "_ZL18glorb_icache_bytesv": 0x42006AD0}), (0x40378000, 0x40378E00))

    def test_the_banks_addresses_outside_the_heaps_table_stop_the_build(self):
        # The SDK's heap start-up reads records between the two table symbols and nowhere else.
        for table in (OTHER_RECORD + bytes(8), bytes(6) + RESERVED + bytes(2)):
            with self.assertRaisesRegex(ValueError, "heap"):
                self.script.check_elf(built(table=table, elsewhere=RESERVED))


class BuiltImage(unittest.TestCase):
    def setUp(self):
        import check_glorb_icache
        self.check = check_glorb_icache.check
        self.elf = built()

    def test_a_complete_image_with_its_elf_passes(self):
        self.assertEqual(self.check(packed(self.elf), self.elf), (0x40378000, 0x40378E00))

    def test_ram_code_inside_the_second_bank_fails(self):
        with self.assertRaisesRegex(ValueError, "0x40374000"):
            self.check(packed(self.elf, ram_code=0x40374000), self.elf)


if __name__ == "__main__":
    unittest.main()
