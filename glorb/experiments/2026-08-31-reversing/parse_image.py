#!/usr/bin/env python3
import struct, sys, os

path = sys.argv[1] if len(sys.argv) > 1 else "/home/tycorc/git/tyclab/tycwled/glorb/firmware/firmware_gma_83_debug.bin"
outdir = sys.argv[2] if len(sys.argv) > 2 else "segments"
os.makedirs(outdir, exist_ok=True)

data = open(path, "rb").read()
assert data[0] == 0xE9, "bad magic"
seg_count = data[1]
entry = struct.unpack_from("<I", data, 4)[0]
chip_id = struct.unpack_from("<H", data, 12)[0]
print(f"segments={seg_count} entry=0x{entry:08x} chip_id={chip_id}")

off = 24  # esp_image_header_t is 24 bytes
segs = []
for i in range(seg_count):
    load_addr, data_len = struct.unpack_from("<II", data, off)
    off += 8
    seg = data[off:off+data_len]
    off += data_len
    segs.append((load_addr, data_len, seg))
    kind = "?"
    if 0x3c000000 <= load_addr < 0x3d000000: kind = "DROM(rodata)"
    elif 0x42000000 <= load_addr < 0x43000000: kind = "IROM(flash.text)"
    elif 0x4037c000 <= load_addr < 0x403e0000: kind = "IRAM"
    elif 0x3fc80000 <= load_addr < 0x3fd00000: kind = "DRAM"
    elif 0x40370000 <= load_addr < 0x4037c000: kind = "RTC/IRAM"
    fn = os.path.join(outdir, f"seg{i}_0x{load_addr:08x}_{kind.split('(')[0].replace('/','-')}.bin")
    open(fn, "wb").write(seg)
    print(f"seg{i}: load=0x{load_addr:08x} len=0x{data_len:08x} ({data_len}) {kind} -> {fn}")

print(f"consumed {off} of {len(data)} bytes")
