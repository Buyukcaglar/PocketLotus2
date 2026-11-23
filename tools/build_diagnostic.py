"""SPDX-License-Identifier: GPL-3.0-or-later
Tiny deterministic ARMv2 assembler for this original diagnostic only.
Unsupported instructions fail; no compiler/toolchain or ROM blobs are needed.
Writes binary, little-endian word hex and an address/opcode listing to build/.
"""
from pathlib import Path
import re
import struct
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x03800000


def reg(s):
    return 15 if s == "pc" else int(s.removeprefix("r"))


def imm(v):
    for rotation in range(16):
        n = ((v << (rotation * 2)) | (v >> ((32 - rotation * 2) % 32))) & 0xffffffff
        if n <= 255:
            return (rotation << 8) | n
    raise ValueError(f"Not an ARM immediate: {v:#x}")


def assemble():
    lines = []
    labels = {}
    offset = 0
    literals = []
    for raw in (ROOT / "firmware/diagnostic.S").read_text().splitlines():
        line = raw.split("@")[0].strip()
        if not line:
            continue
        if line.endswith(":"):
            labels[line[:-1]] = BASE + offset
            continue
        lines.append((offset, line))
        if line.startswith(".word"):
            offset += 4 * len(line[5:].split(","))
        else:
            offset += 4
        if re.match(r"ldr .*?=", line):
            literal = line.split("=", 1)[1]
            if literal not in literals:
                literals.append(literal)
    pool = {s: BASE + offset + 4 * i for i, s in enumerate(literals)}
    words, listing = [], []
    def value(s):
        return labels[s] if s in labels else int(s, 0)
    for off, line in lines:
        if line.startswith(".word"):
            out = [value(s.strip()) for s in line[5:].split(",")]
        elif re.match(r"b(ne|eq)? ", line):
            op, target = line.split()
            condition = {"b": 14, "beq": 0, "bne": 1}[op]
            delta = (value(target) - (BASE + off + 8)) // 4
            out = [(condition << 28) | 0x0a000000 | (delta & 0xffffff)]
        elif line.startswith("stmia "):
            rn, first, last = re.fullmatch(r"stmia (r\d+)!, \{(r\d+)-(r\d+)\}", line).groups()
            mask = sum(1 << i for i in range(reg(first), reg(last)+1))
            out = [0xe8a00000 | reg(rn) << 16 | mask]
        elif "=" in line:
            rd, literal = re.match(r"ldr (\w+), =(.*)", line).groups()
            delta = pool[literal] - (BASE + off + 8)
            assert 0 <= delta < 4096
            out = [0xe59f0000 | reg(rd) << 12 | delta]
        elif "[" in line:
            op, rd, rn, displacement = re.match(r"(ldr|str|ldrb|strb) (\w+), \[(\w+)(?:, #(\w+))?\]", line).groups()
            disp = int(displacement, 0) if displacement else 0
            assert disp < 4096
            out = [0xe5800000 | (op.startswith("ldr") << 20) | (op.endswith("b") << 22)
                   | reg(rn) << 16 | reg(rd) << 12 | disp]
        else:
            op, args = line.split(" ", 1)
            parts = [s.strip() for s in args.split(",")]
            opcode = {"mov": 13, "add": 4, "subs": 2, "cmp": 10, "and": 0, "orr": 12}[op]
            rd = 0 if op == "cmp" else reg(parts[0])
            rn = 0 if op == "mov" else reg(parts[0] if op == "cmp" else parts[1])
            operand = parts[-1]
            immediate = operand.startswith("#")
            bits = imm(int(operand[1:], 0)) if immediate else reg(operand)
            out = [0xe0000000 | immediate << 25 | opcode << 21 | (op in ("cmp", "subs")) << 20
                   | rn << 16 | rd << 12 | bits]
        for i, word in enumerate(out):
            listing.append(f"{BASE+off+i*4:08x} {word:08x} {line}")
        words.extend(out)
    words.extend(value(s) for s in literals)
    # Fill to a cache-line boundary; unused words trap in an ARM self branch.
    while len(words) % 4:
        words.append(0xeafffffe)
    out = ROOT / "build/diagnostic"
    out.mkdir(parents=True, exist_ok=True)
    blob = b"".join(struct.pack("<I", w) for w in words)
    (out / "diagnostic.bin").write_bytes(blob)
    (out / "diagnostic.hex").write_text("\n".join(f"{w:08x}" for w in words) + "\n")
    (out / "diagnostic_size.vh").write_text(f"`define DIAGNOSTIC_WORDS {len(words)}\n")
    (out / "diagnostic.lst").write_text("\n".join(listing) + "\n")
    result = dict(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), base=hex(BASE), labels=labels)
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    assemble()
