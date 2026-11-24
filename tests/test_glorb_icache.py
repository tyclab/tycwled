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


def image(segments, built_from=b"", chip=9):
    """An ESP32 application image: header, (load address, bytes) segments, checksum and SHA-256. The first
    segment starts with the application description, which names the ELF the image was made from."""
    out = bytearray(struct.pack("<BBBBI", 0xE9, len(segments), 2, 0x3F, 0x40378000)
                    + bytes(4) + struct.pack("<H", chip) + bytes(9) + b"\x01")
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


def built(table=OTHER_RECORD + RESERVED, symbols=LAYOUT, elsewhere=b"", ram=RAM, table_parts=1):
    """An ELF with RAM code at 0x40378000, the SDK's table of reserved memory at 0x3c0f0100 (in one section or
    cut into several) and other read-only data at 0x3c0f0200."""
    step = len(table) // table_parts
    parts = {0x3C0F0100 + at: table[at:at + step] for at in range(0, len(table), step)}
    return elf(symbols, {**parts, 0x3C0F0200: elsewhere + bytes(8), 0x40378000: ram})


def packed(source, ram_code=0x40378000, leave_out=None, chip=9):
    """The image of a built() ELF: read-only data from 0x3c0f0020 on, flash code, RAM code."""
    script = load(USERMOD / "icache_32kb.py", "icache_32kb")
    rodata = bytearray(0x200 - 0x20 - 0xB0 + 64)
    ram = b""
    for address, data in script.loaded(source):
        if address == leave_out:
            continue
        if address >= 0x40000000:
            ram = data
        else:
            at = address - 0x3C0F0020 - 0xB0
            rodata[at:at + len(data)] = data
    return image([(0x3C0F0020, bytes(rodata)), (0x42000020, bytes(64)), (ram_code, ram or bytes(64))], source, chip)


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

    def test_a_switch_symbol_without_code_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "no code"):
            self.script.check_elf(built(ram=bytes(0x400)))

    def test_a_helper_that_runs_with_the_caches_on_may_lie_in_flash(self):
        # Built without inlining (-Og), the info row's glorb_icache_bytes() is a function of its own, in flash.
        self.assertEqual(self.layout({**LAYOUT, "_ZL18glorb_icache_bytesv": 0x42006AD0}), (0x40378000, 0x40378E00))

    def test_the_banks_addresses_outside_the_heaps_table_stop_the_build(self):
        # The SDK's heap start-up reads records between the two table symbols and nowhere else.
        for table in (OTHER_RECORD + bytes(8), bytes(6) + RESERVED + bytes(2)):
            with self.assertRaisesRegex(ValueError, "heap"):
                self.script.check_elf(built(table=table, elsewhere=RESERVED))

    def test_a_table_that_spans_two_sections_is_read_whole(self):
        self.assertEqual(self.script.check_elf(built(table_parts=2)), (0x40378000, 0x40378E00))

    def test_a_bank_reserved_twice_stops_the_build(self):
        # The heap's start-up sorts the records and stops when one reaches into the next.
        with self.assertRaisesRegex(ValueError, "2 records"):
            self.script.check_elf(built(table=RESERVED + RESERVED))

    def test_overlapping_reservations_stop_the_build(self):
        with self.assertRaisesRegex(ValueError, "reaches into"):
            self.script.check_elf(built(table=struct.pack("<II", 0x40370000, 0x40376000) + RESERVED))

    def test_an_elf_without_the_table_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "heap"):
            self.script.check_elf(built(symbols={"_iram_start": 0x40378000, SWITCH: 0x40378E00}))


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

    def test_an_image_without_ram_code_fails(self):
        with self.assertRaisesRegex(ValueError, "no RAM code"):
            self.check(image([(0x3C0F0020, b"rodata"), (0x42000020, bytes(64))], self.elf), self.elf)

    def test_an_image_cut_short_fails(self):
        whole = packed(self.elf)
        for length in (len(whole) - 1, len(whole) - 33, len(whole) - 60, 0x100, 20):
            with self.assertRaisesRegex(ValueError, "image"):
                self.check(whole[:length], self.elf)

    def test_an_image_with_a_changed_byte_fails(self):
        changed = bytearray(packed(self.elf))
        changed[0x120] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum|SHA-256"):
            self.check(bytes(changed), self.elf)

    def test_an_image_for_another_chip_fails(self):
        with self.assertRaisesRegex(ValueError, "ESP32-S3"):
            self.check(packed(self.elf, chip=2), self.elf)

    def test_the_elf_of_another_build_fails(self):
        with self.assertRaisesRegex(ValueError, "another build"):
            self.check(packed(self.elf), built(elsewhere=b"other"))

    def test_an_image_that_lacks_what_its_elf_loads_fails(self):
        # The heap's table and the switch are checked on the ELF, so the image has to hold the ELF's bytes.
        for left_out, message in ((0x40378000, "lacks"), (0x3C0F0100, "differs")):
            with self.assertRaisesRegex(ValueError, message):
                self.check(packed(self.elf, leave_out=left_out), self.elf)

    def test_an_elf_without_the_heap_reservation_fails(self):
        # The bank's addresses somewhere in the image are no reservation.
        unreserved = built(table=OTHER_RECORD + bytes(8), elsewhere=RESERVED)
        with self.assertRaisesRegex(ValueError, "heap"):
            self.check(packed(unreserved), unreserved)


if __name__ == "__main__":
    unittest.main()
