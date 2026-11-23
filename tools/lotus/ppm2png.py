#!/usr/bin/env python3
"""Convert host-runner PPM frames to PNG (standard library only). usage: ppm2png.py FILE..."""
import struct
import sys
import zlib
from pathlib import Path


def convert(path: Path) -> None:
    data = path.read_bytes()
    parts = data.split(b"\n", 3)
    w, h = map(int, parts[1].split())
    rgb = parts[3]
    raw = b"".join(b"\0" + rgb[y * w * 3 : (y + 1) * w * 3] for y in range(h))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.with_suffix(".png").write_bytes(png)


for name in sys.argv[1:]:
    convert(Path(name))
