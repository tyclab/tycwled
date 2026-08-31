#!/usr/bin/env bash
# Disassemble a target function from the IROM segment of the GLORB firmware.
# Usage: ./disasm.sh <vaddr-hex> <num-instructions>
# Requires: radare2 (nix shell nixpkgs#radare2). ESP32-S3 = Xtensa LX7 LE.
# Segments produced by parse_image.py; IROM (.flash.text) loads at 0x42000020.
set -euo pipefail
SEG="${SEG:-segments_debug/seg2_0x42000020_IROM.bin}"
ADDR="$1"; N="${2:-120}"
r2 -e scr.color=0 -e asm.lines=false -e asm.bytes=true \
   -a xtensa -b 32 -m 0x42000020 -qc "s $ADDR; pd $N" "$SEG" 2>/dev/null
