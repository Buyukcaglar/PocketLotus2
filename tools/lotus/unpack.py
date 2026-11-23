#!/usr/bin/env python3
"""Unpack the Lotus Turbo Challenge 2 (Archimedes) program from user media.

Reads the files extracted from the user's own disk 1 (analysis/media/F1023201/
extracted/!LOTUS) and writes the decrypted program images to build/lotus/.
Nothing produced here may be published: outputs are derived game content.

The X Lock loader has three layers, all reproduced statically here:

1. `Loader` (absolute, &8000): XORs &8104..&8BE8 with &4C into a relocated
   block (the JASPP launcher places it at &8E300).
2. Three chained rolling XOR passes over that block (the BASIC loop in the
   JASPP 0-2 `!Run`), each keyed by 44 bytes of the previous layer.
3. The stage-2 code loads `Logo` to &70000 and `Graphics` to &8000 and XORs
   each with (length & 255) ^ 44 bytes of its own decrypt loop ^ a key byte
   that the original compares against the protected sector read. The expected
   value is stored in the loader itself, so the disk is not needed.

`Logo` is the start-up stub (entry &70000). `Graphics` is a compressed image
that the stub expands; expansion is done by running the stub (see port/).
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "analysis/media/F1023201/extracted/!LOTUS"
OUT = ROOT / "build/lotus"

LOADER_SHA256 = "10d14e0d2bb8c8ed7edd5097943c94b25d5b18846186e26427570372a4a54711"
STAGE2_BASE = 0x8E300


def stage2(loader: bytes) -> bytes:
    block = bytearray(b ^ 0x4C for b in loader[0x104:0xBE8])
    mem = block + bytearray(0x1100)
    a, e, z = 0x8E30C, 0x58, 0xA80
    for _ in range(3):
        for b in range(a + 0x58, 0x8EFD4 + 1, 0x2C):
            for c in range(0x2C):
                i = b - STAGE2_BASE + c
                mem[i] = (mem[i] ^ z ^ mem[a - STAGE2_BASE + c + 0x28]) & 0xFF
        z -= e
        a += e
        e += 0x2C
    return bytes(mem[: len(block)])


def payload(st2: bytes, data: bytes, key_addr: int) -> bytes:
    disc_key = st2[0x8ECF8 - STAGE2_BASE]
    key = st2[key_addr - STAGE2_BASE : key_addr - STAGE2_BASE + 0x2C]
    n = len(data) & 0xFF
    return bytes(b ^ n ^ key[i % 0x2C] ^ disc_key for i, b in enumerate(data))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    loader = (args.src / "Loader").read_bytes()
    digest = hashlib.sha256(loader).hexdigest()
    if digest != LOADER_SHA256:
        raise SystemExit(f"unexpected Loader hash {digest}")
    st2 = stage2(loader)
    if b"X Lock.(C) Daniel Simms" not in st2:
        raise SystemExit("stage 2 decryption failed")
    entry = struct.unpack_from("<I", st2, 0x8EDD8 - STAGE2_BASE)[0]
    stub = payload(st2, (args.src / "Logo").read_bytes(), 0x8E950)
    packed = payload(st2, (args.src / "Graphics").read_bytes(), 0x8E9A4)
    if entry != 0x70000 or stub[3] != 0xEA:
        raise SystemExit("stub decryption failed")

    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {"loader_stage2.bin": st2, "stub_70000.bin": stub, "packed_8000.bin": packed}
    manifest = {"entry": entry, "stub_load": 0x70000, "packed_load": 0x8000, "files": {}}
    for name, blob in outputs.items():
        (args.out / name).write_bytes(blob)
        manifest["files"][name] = {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}
    (args.out / "unpack.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
