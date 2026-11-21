"""The GLORB build runs with a 32 KB instruction cache.

Measured on an ESP32-S3 on 2026-11-21: with the SDK's 16 KB instruction cache the fleet image's main
loop runs 629-663 times a second, with 32 KB 3,010-3,055 times. The second cache bank's RAM
(0x40374000-0x40378000) holds code in the stock memory layout, so three things have to change together:
the linker script, the heap reservation and the switch.
"""
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USERMOD = ROOT / "glorb/usermod/glorb_fx"
SOURCE = USERMOD / "glorb_fx.cpp"
OVERRIDE = USERMOD / "platformio_override.ini"
sys.path.insert(0, str(ROOT / "fleet"))

STOCK_LINE = ("  iram0_0_seg (RX) : org = (0x40370000 + 0x4000), "
              "len = (((0x403CC700 - (0x40378000 - 0x3FC88000)) - 0x3FC88000) + 0x8000 - 0x4000)")
STOCK = "MEMORY\n{\n" + STOCK_LINE + "\n  dram0_0_seg (RW) : org = (0x3FC88000), len = 0x44700\n}\n"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image(segments):
    """An ESP32 application image: the 24-byte header, then (load address, bytes) segments."""
    out = bytearray(struct.pack("<BBBBI", 0xE9, len(segments), 2, 0x3F, 0x40378000) + bytes(16))
    for address, data in segments:
        out += struct.pack("<II", address, len(data)) + data
    return bytes(out)


RESERVED = struct.pack("<II", 0x40374000, 0x40378000)


def elf(symbols):
    """A 32-bit little-endian ELF that holds nothing but a symbol table with these names and addresses."""
    names, entries = b"\0", [bytes(16)]
    for name, value in symbols.items():
        entries.append(struct.pack("<IIIBBH", len(names), value, 0, 2, 0, 1))
        names += name.encode() + b"\0"
    table = b"".join(entries)
    section_names = b"\0.symtab\0.strtab\0.shstrtab\0"
    at_names = 52 + len(table)
    at_section_names = at_names + len(names)

    def section(name, kind, offset, size, link=0, entry=0):
        return struct.pack("<10I", name, kind, 0, 0, offset, size, link, 0, 1, entry)

    sections = [bytes(40), section(1, 2, 52, len(table), link=2, entry=16), section(9, 3, at_names, len(names)),
                section(17, 3, at_section_names, len(section_names))]
    header = (b"\x7fELF\x01\x01\x01" + bytes(9)
              + struct.pack("<HHIIIIIHHHHHH", 2, 94, 1, 0, 0, at_section_names + len(section_names), 0, 52, 0, 0, 40,
                            len(sections), 3))
    return header + table + names + section_names + b"".join(sections)


SWITCH = "_ZL17glorb_icache_32kbv"


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


class Usermod(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()
        start = self.source.index("#ifdef GLORB_ICACHE_32KB")
        self.guarded = self.source[start:self.source.index("#endif", start)]

    def test_reservation_and_switch_are_compiled_only_with_the_linker_script(self):
        # Reserving the bank while code still lives there aborts the boot (overlapping reserved regions).
        self.assertIn("SOC_RESERVE_MEMORY_REGION(0x40374000, 0x40378000, glorb_icache_bank1);", self.guarded)
        self.assertEqual(self.source.count("SOC_RESERVE_MEMORY_REGION"), 1)
        self.assertEqual(self.source.count("Cache_Set_ICache_Mode"), 1)
        self.assertIn("Cache_Set_ICache_Mode", self.guarded)
        # The define comes from the script that swaps the linker script, never from the build flags.
        self.assertNotRegex(OVERRIDE.read_text(), r"-D\s*GLORB_ICACHE_32KB")
        self.assertNotRegex((ROOT / "fleet/platformio_override.ini").read_text(), r"-D\s*GLORB_ICACHE_32KB")
        self.assertIn("pre:usermods/glorb_fx/icache_32kb.py", OVERRIDE.read_text())

    def test_the_switch_is_kept_out_of_line_in_ram(self):
        # Flash is unreachable while the caches are stopped; an inlined copy would sit in flash. Whether the
        # built function really lies in RAM is checked on the ELF (BuiltElf below).
        self.assertRegex(self.guarded, r"static void IRAM_ATTR __attribute__\(\(noinline\)\) glorb_icache_32kb\(\)")
        # A stock memory layout with the define stops in heap start-up, before any check in setup() could
        # run: the layout is checked at build time, not on the lamp.
        self.assertNotIn("_iram_start", self.source)

    def test_the_info_page_reads_the_cache_size_back_from_the_chip(self):
        self.assertIn('user.createNestedArray(F("Main loop"))', self.source)
        self.assertIn("Cache_Get_Mode(&mode);", self.guarded)
        self.assertNotIn("icache32kb", self.source)


class BuiltElf(unittest.TestCase):
    def setUp(self):
        self.script = load(USERMOD / "icache_32kb.py", "icache_32kb")

    def test_ram_code_after_both_banks_with_the_switch_in_ram_passes(self):
        start, switch = self.script.check_layout(self.script.symbols(elf(
            {"_iram_start": 0x40378000, SWITCH: 0x40378E00, "loop": 0x42001234})))
        self.assertEqual((start, switch), (0x40378000, 0x40378E00))

    def test_ram_code_inside_the_second_bank_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "memory.ld"):
            self.script.check_layout(self.script.symbols(elf({"_iram_start": 0x40374000, SWITCH: 0x40374E00})))

    def test_a_switch_in_flash_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "flash"):
            self.script.check_layout(self.script.symbols(elf({"_iram_start": 0x40378000, SWITCH: 0x42012340})))

    def test_an_inlined_switch_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "inlined"):
            self.script.check_layout(self.script.symbols(elf({"_iram_start": 0x40378000, "loop": 0x42001234})))

    def test_something_that_is_no_elf_stops_the_build(self):
        with self.assertRaises(ValueError):
            self.script.symbols(b"\xe9" + bytes(100))


class BuiltImage(unittest.TestCase):
    def setUp(self):
        import check_glorb_icache
        self.check = check_glorb_icache.check

    def test_ram_code_above_the_bank_with_the_reservation_passes(self):
        self.check(image([(0x3C0F0020, b"rodata" + RESERVED), (0x42000020, bytes(64)), (0x40378000, bytes(64))]))

    def test_ram_code_inside_the_second_bank_fails(self):
        with self.assertRaisesRegex(ValueError, "0x40374000"):
            self.check(image([(0x3C0F0020, RESERVED), (0x42000020, bytes(64)), (0x40374000, bytes(64))]))

    def test_a_missing_heap_reservation_fails(self):
        with self.assertRaisesRegex(ValueError, "reserv"):
            self.check(image([(0x3C0F0020, b"rodata"), (0x42000020, bytes(64)), (0x40378000, bytes(64))]))

    def test_an_image_without_ram_code_fails(self):
        with self.assertRaisesRegex(ValueError, "no RAM code"):
            self.check(image([(0x3C0F0020, RESERVED), (0x42000020, bytes(64))]))


if __name__ == "__main__":
    unittest.main()
