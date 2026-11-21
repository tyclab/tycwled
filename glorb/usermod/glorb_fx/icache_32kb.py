"""PlatformIO pre-script: link the GLORB build for a 32 KB instruction cache.

The framework's ESP32-S3 SDK is prebuilt for a 16 KB instruction cache and puts RAM code into the RAM of
the unused second cache bank (0x40374000-0x40378000). This script links against a copy of the framework's
memory.ld whose RAM code starts after both banks, and defines GLORB_ICACHE_32KB so that glorb_fx reserves
the bank from the heap and switches the cache at start. The define must come from here and nowhere else:
the reservation without this memory layout overlaps the code's own reservation and stops the boot.
"""
from pathlib import Path

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


def configure(env):
    framework = Path(env.PioPlatform().get_package_dir("framework-arduinoespressif32"))
    out = Path(env.subst("$BUILD_DIR")) / "glorb_icache_32kb"
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory.ld").write_text(patch((framework / "tools/sdk/esp32s3/ld/memory.ld").read_text()))
    # The framework appends its own ld directory later; the linker takes the first memory.ld it finds.
    env.Prepend(LIBPATH=[str(out)])
    env.Append(CPPDEFINES=["GLORB_ICACHE_32KB"])


try:
    Import("env")  # noqa: F821  SCons provides Import and, through it, env
except NameError:  # imported by the tests
    pass
else:
    configure(env)  # noqa: F821
