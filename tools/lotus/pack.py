#!/usr/bin/env python3
"""Build the Lotus asset pack (build/lotus/lotus2.dat) from the user's extracted disks.

The pack is the single data file the Pocket application loads. It holds the
decrypted start-up stub and packed program (from tools/lotus/unpack.py) and
every game file the program asks RISC OS for. It is derived game content and
must not be published.

Layout: "LTC2PAK1", u32 count, then count entries of {char name[40], u32 offset,
u32 size}, then file data. Names are lower case with '/' separators, relative to
the game directory: "krisalis", "disk1/files1/file04", "boot/stub".
"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/lotus"
DISK1 = ROOT / "analysis/media/F1023201/extracted/!LOTUS"
DISK2 = ROOT / "analysis/media/F1023202/extracted"
SKIP = {"loader", "logo", "graphics", "!run", "!sprites", "wimpbanner", "memmod", "joymod"}


def collect():
    files = {
        "boot/stub": (BUILD / "stub_70000.bin").read_bytes(),
        "boot/packed": (BUILD / "packed_8000.bin").read_bytes(),
    }
    for base in (DISK1, DISK2):
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(base).as_posix().lower()
            if name in SKIP or name.startswith("!") or "/" not in name and base is DISK2:
                continue
            files.setdefault(name, path.read_bytes())
    return files


def main():
    files = collect()
    header = 12 + 48 * len(files)
    table, blobs, offset = [], [], header
    for name, data in files.items():
        raw = name.encode("ascii")
        if len(raw) > 39:
            raise SystemExit(f"name too long: {name}")
        table.append(struct.pack("<40sII", raw, offset, len(data)))
        pad = (-len(data)) % 4
        blobs.append(data + b"\0" * pad)
        offset += len(data) + pad
    out = BUILD / "lotus2.dat"
    out.write_bytes(b"LTC2PAK1" + struct.pack("<I", len(files)) + b"".join(table) + b"".join(blobs))
    print(f"{out}: {len(files)} files, {offset} bytes")


if __name__ == "__main__":
    main()
