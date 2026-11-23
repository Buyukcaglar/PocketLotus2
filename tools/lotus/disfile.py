#!/usr/bin/env python3
"""Disassemble a range of any ARM binary file: disfile.py FILE START END [BASE].

Offsets are hexadecimal file offsets; BASE is added to shown addresses.
"""
import struct
import sys

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs


def main():
    path, start, end = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    base = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0
    data = open(path, "rb").read()
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for off in range(start, min(end, len(data) - 3), 4):
        word = struct.unpack_from("<I", data, off)[0]
        text = ".word"
        if (word >> 28) == 15:
            text = "nop (NV)"
        else:
            for insn in md.disasm(data[off:off + 4], base + off):
                text = f"{insn.mnemonic} {insn.op_str}"
        chars = "".join(chr(b) if 32 <= b < 127 else "." for b in data[off:off + 4])
        print(f"{base + off:06x}: {word:08x} {chars} {text}")


if __name__ == "__main__":
    main()
