"""PlatformIO pre-script: link the GLORB build for a 32 KB instruction cache.

The framework's ESP32-S3 SDK is prebuilt for a 16 KB instruction cache and puts RAM code into the RAM of
the unused second cache bank (0x40374000-0x40378000). This script links against a copy of the framework's
memory.ld whose RAM code starts after both banks, and defines GLORB_ICACHE_32KB so that glorb_fx reserves
the bank from the heap and switches the cache at start. The define must come from here and nowhere else:
the reservation without this memory layout overlaps the code's own reservation and stops the boot.

After linking, the script reads the ELF and stops the build when RAM code still starts inside the second
bank (the linker took another memory.ld), when the cache switch function does not lie in RAM (it runs while
flash is unreachable; inlined into its caller it would sit in flash and stop the lamp at start) or when the
bank is no record of the table the SDK's heap start-up reads (the heap would hand out the cache's RAM).
"""
from pathlib import Path
import struct

BANK = (0x40374000, 0x40378000)
RAM_CODE = (0x40378000, 0x403E0000)
SWITCH = "glorb_icache_32kb"

STOCK = ("iram0_0_seg (RX) : org = (0x40370000 + 0x4000), "
         "len = (((0x403CC700 - (0x40378000 - 0x3FC88000)) - 0x3FC88000) + 0x8000 - 0x4000)")
MOVED = ("iram0_0_seg (RX) : org = (0x40370000 + 0x8000), "
         "len = (((0x403CC700 - (0x40378000 - 0x3FC88000)) - 0x3FC88000) + 0x8000 - 0x8000)")


def patch(text):
    """The framework's memory.ld with RAM code starting at 0x40378000."""
    if text.count(STOCK) != 1:
        raise ValueError("memory.ld of this framework no longer has the 16 KB instruction cache layout "
                         "this script was written for; check the cache size and the layout again")
    return text.replace(STOCK, MOVED)


def sections(elf):
    """The section headers of a 32-bit little-endian ELF: name, type, flags, address, offset, size, link, ..."""
    if elf[:6] != b"\x7fELF\x01\x01":
        raise ValueError("not a 32-bit little-endian ELF")
    table, = struct.unpack_from("<I", elf, 0x20)
    entry, count = struct.unpack_from("<HH", elf, 0x2E)
    return [struct.unpack_from("<10I", elf, table + index * entry) for index in range(count)]


def symbols(elf):
    """Name to address of every symbol in a 32-bit little-endian ELF."""
    headers = sections(elf)
    found = {}
    for _, kind, _, _, offset, size, link, _, _, _ in headers:
        if kind != 2:  # SHT_SYMTAB
            continue
        names = headers[link][4]
        for at in range(offset, offset + size, 16):
            name, value = struct.unpack_from("<II", elf, at)
            found[elf[names + name:elf.index(b"\0", names + name)].decode()] = value
    return found


def check_layout(found):
    """RAM code starts after both cache banks and the cache switch function lies in RAM."""
    start = found.get("_iram_start")
    if start is None or start < RAM_CODE[0]:
        raise ValueError(f"RAM code starts at {start if start is None else hex(start)}, inside the instruction "
                         "cache's RAM: the linker did not take this script's memory.ld")
    # The compiler's copies of the function (name.isra.0 and the like) count; the info row's helper and the
    # heap record, which only share the prefix, do not: they are used with the caches on.
    switches = {name: address for name, address in found.items() if SWITCH in name}
    if not switches:
        raise ValueError(f"no {SWITCH} function in the ELF: the cache switch was inlined into its caller, "
                         "which runs from flash")
    for name, address in switches.items():
        if not RAM_CODE[0] <= address < RAM_CODE[1]:
            raise ValueError(f"{name} at {address:#x} lies in flash, which is unreachable while it runs")
    return start, min(switches.values())


def check_reservation(elf, found):
    """The second bank is a record of the table the SDK's heap start-up reads (soc_get_reserved_regions)."""
    try:
        start, end = found["soc_reserved_memory_region_start"], found["soc_reserved_memory_region_end"]
    except KeyError:
        raise ValueError("the ELF has no table of memory reserved from the heap") from None
    table = next((elf[offset + start - address:offset + end - address]
                  for _, kind, _, address, offset, size, *_ in sections(elf)
                  if kind == 1 and address <= start <= end <= address + size), b"")  # SHT_PROGBITS
    if BANK not in [struct.unpack_from("<II", table, at) for at in range(0, len(table) - 7, 8)]:
        raise ValueError(f"{BANK[0]:#x}-{BANK[1]:#x} is no record of the heap's table of reserved memory "
                         f"({start:#x}-{end:#x}): the heap would hand out the second cache bank's RAM")


def check_elf(elf):
    found = symbols(elf)
    layout = check_layout(found)
    check_reservation(elf, found)
    return layout


def verify(target, source, env):
    start, switch = check_elf(Path(str(target[0])).read_bytes())
    print(f"glorb_fx: RAM code from {start:#x}, cache switch at {switch:#x}, second bank reserved from the heap")


def configure(env):
    framework = Path(env.PioPlatform().get_package_dir("framework-arduinoespressif32"))
    out = Path(env.subst("$BUILD_DIR")) / "glorb_icache_32kb"
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory.ld").write_text(patch((framework / "tools/sdk/esp32s3/ld/memory.ld").read_text()))
    # The framework appends its own ld directory later; the linker takes the first memory.ld it finds.
    env.Prepend(LIBPATH=[str(out)])
    env.Append(CPPDEFINES=["GLORB_ICACHE_32KB"])
    env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", verify)


try:
    Import("env")  # noqa: F821  SCons provides Import and, through it, env
except NameError:  # imported by the tests
    pass
else:
    configure(env)  # noqa: F821
