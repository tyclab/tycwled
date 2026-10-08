#!/usr/bin/env bash
# Usage: ./disasm.sh <vaddr-hex> <num-instructions>; needs radare2 on PATH.
# Reads the IROM segment written by parse_image.py, which loads at 0x42000020.
set -euo pipefail
SEG="${SEG:-segments_debug/seg2_0x42000020_IROM.bin}"
ADDR="$1"; N="${2:-120}"
r2 -e scr.color=0 -e asm.lines=false -e asm.bytes=true \
   -a xtensa -b 32 -m 0x42000020 -qc "s $ADDR; pd $N" "$SEG" 2>/dev/null
