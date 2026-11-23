#!/usr/bin/env python3
"""Disassemble a range of the expanded game image (build/lotus/game_image.bin, base &8000).

usage: disasm.py START [END]   (hex addresses)
"""
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

BASE = 0x8000
img = (Path(__file__).resolve().parents[2] / "build/lotus/game_image.bin").read_bytes()
start = int(sys.argv[1], 16)
end = int(sys.argv[2], 16) if len(sys.argv) > 2 else start + 0x80
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
for a in range(start, end, 4):
    raw = img[a - BASE : a - BASE + 4]
    (w,) = struct.unpack("<I", raw)
    ins = next(md.disasm(raw, a), None)
    text = f"{ins.mnemonic} {ins.op_str}" if ins else "??"
    if w >> 28 == 0xF:
        text = "nop (NV)"
    print(f"{a:06x} {w:08x} {text}")
