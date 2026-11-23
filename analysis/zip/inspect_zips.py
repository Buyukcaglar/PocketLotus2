#!/usr/bin/env python3
"""Read-only, streaming inventory of supplied Lotus RiscPkg ZIP archives.

Writes JSON evidence only. Never extracts, launches, rewrites, or patches media.
Offsets into source text are zero-based byte positions in uncompressed members;
ZIP header/data offsets are zero-based byte positions in the original archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
LOTUS_PREFIX = "Apps/Games/!LOTUS/"
TEXT_MEMBERS = {"RiscPkg/Control", "RiscPkg/Copyright", LOTUS_PREFIX + "!Run"}
SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".s", ".asm", ".bas", ".basic", ".pas", ".f", ".f90", ".v", ".sv"}
TYPE_NAMES = {0xFFF: "text", 0xFEB: "Obey script", 0xFF9: "sprite", 0xFFA: "RISC OS module", 0xFF8: "absolute executable", 0xFFD: "data"}
EXTRA_SPEC = "https://raw.githubusercontent.com/madler/unzip/master/proginfo/extrafld.txt"


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def snapshot(path: Path) -> dict:
    stat = path.stat()
    return {"sha256": hash_file(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def extra_fields(extra: bytes, archive_base: int | None = None) -> list[dict]:
    fields, pos = [], 0
    while pos + 4 <= len(extra):
        tag, length = struct.unpack_from("<HH", extra, pos)
        payload = extra[pos + 4:pos + 4 + length]
        item = {"id_hex": f"0x{tag:04X}", "length": length, "extra_offset": pos,
                "payload_hex": payload.hex(), "complete": len(payload) == length}
        if archive_base is not None:
            item["archive_offset"] = archive_base + pos
        if tag == 0x4341 and len(payload) == 20 and payload[:4] == b"ARC0":
            load, execute, attr, reserved = struct.unpack_from("<IIII", payload, 4)
            typed = (load & 0xFFF00000) == 0xFFF00000
            filetype = ((load >> 8) & 0xFFF) if typed else None
            item["acorn"] = {"signature": "ARC0", "load_hex": f"0x{load:08X}",
                "exec_hex": f"0x{execute:08X}", "attributes_hex": f"0x{attr:08X}",
                "reserved_hex": f"0x{reserved:08X}", "has_encoded_filetype": typed,
                "filetype_hex": f"0x{filetype:03X}" if typed else None,
                "filetype_name": TYPE_NAMES.get(filetype, "unlabelled in this inventory")}
        fields.append(item)
        pos += 4 + length
    if pos != len(extra):
        fields.append({"malformed_or_trailing_hex": extra[pos:].hex(), "extra_offset": pos})
    return fields


def text_evidence(data: bytes) -> dict:
    lines, offset = [], 0
    for number, raw in enumerate(data.splitlines(keepends=True), 1):
        lines.append({"line": number, "byte_start": offset, "byte_end_exclusive": offset + len(raw),
                      "text": raw.rstrip(b"\r\n").decode("latin1")})
        offset += len(raw)
    return {"encoding": "Latin-1 lossless byte mapping; raw byte SHA is authoritative",
            "text": data.decode("latin1"), "lines": lines}


def parse_control(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            out[key] = value.strip()
    return out


def classify(name: str, acorn: dict | None, prefix: bytes, ratio: float) -> str:
    ft = acorn.get("filetype_hex") if acorn else None
    if name.startswith("RiscPkg/"):
        return "package metadata text"
    if name == LOTUS_PREFIX + "!Run":
        return "readable Obey launcher/compatibility patch script; contains inline BASIC in 0-1/0-2"
    if prefix.startswith(b"\x1f\x8b\x08"):
        return "gzip stream; inner disk-image comparison is in comparison.json"
    if ft == "0xFF8":
        return "binary absolute executable by RISC OS metadata"
    if ft == "0xFFA":
        return "binary module by RISC OS metadata"
    if ft == "0xFF9":
        return "sprite resource by RISC OS metadata"
    if ratio < 0.8:
        return "binary resource/data; exact internal semantic format not inferred"
    return "unclassified text-like payload; requires manual review"


def inspect(path: Path) -> dict:
    before = snapshot(path)
    members, warnings = [], []
    with path.open("rb") as archive, zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        names = Counter(i.filename for i in infos)
        warnings.extend("Duplicate member: " + name for name, count in names.items() if count > 1)
        for info in infos:
            name = info.filename
            if info.flag_bits & 1:
                raise ValueError("Encrypted member: " + name)
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name:
                warnings.append("Suspicious member path (not extracted): " + name)
            archive.seek(info.header_offset)
            local_header = archive.read(30)
            if local_header[:4] != b"PK\x03\x04":
                raise ValueError("Invalid local header: " + name)
            filename_len, extra_len = struct.unpack_from("<HH", local_header, 26)
            local_name = archive.read(filename_len)
            local_extra = archive.read(extra_len)
            compressed_offset = info.header_offset + 30 + filename_len + extra_len
            extra = extra_fields(info.extra)
            acorn = next((e["acorn"] for e in extra if "acorn" in e), None)
            h, crc, length, printable, nul, linebreak = hashlib.sha256(), 0, 0, 0, 0, 0
            prefix, text = bytearray(), bytearray()
            with zf.open(info, "r") as stream:
                for block in iter(lambda: stream.read(65536), b""):
                    h.update(block)
                    crc = zlib.crc32(block, crc)
                    length += len(block)
                    printable += sum(v in (9, 10, 13) or 32 <= v < 127 for v in block)
                    nul += block.count(0)
                    linebreak += block.count(10)
                    if len(prefix) < 64:
                        prefix.extend(block[:64-len(prefix)])
                    if name in TEXT_MEMBERS:
                        text.extend(block)
            if length != info.file_size or crc != info.CRC:
                raise ValueError("Member size/CRC mismatch: " + name)
            ratio = printable / length if length else 1.0
            suffix = PurePosixPath(name).suffix.lower()
            row = {"name": name, "is_directory": info.is_dir(), "size": length,
                "compressed_size": info.compress_size, "compression_method": info.compress_type,
                "sha256": h.hexdigest(), "crc32_hex": f"{crc:08x}", "zip_crc_validated": True,
                "local_header_offset": info.header_offset, "compressed_data_offset": compressed_offset,
                "compressed_data_end_exclusive": compressed_offset + info.compress_size,
                "local_filename_hex": local_name.hex(), "zip_datetime": list(info.date_time),
                "create_system": info.create_system, "flag_bits": info.flag_bits,
                "external_attr_hex": f"0x{info.external_attr:08X}", "central_extra_hex": info.extra.hex(),
                "local_extra_hex": local_extra.hex(), "extra_fields": extra,
                "local_extra_fields": extra_fields(local_extra, info.header_offset + 30 + filename_len),
                "acorn": acorn, "first_64_bytes_hex": prefix.hex(),
                "payload_shape": {"full_ascii_printable_fraction": round(ratio, 8), "nul_bytes": nul,
                                  "linefeeds": linebreak},
                "source_scan": {"under_exact_lotus_app_tree": name.startswith(LOTUS_PREFIX),
                    "extensionless": not suffix, "source_suffix_candidate": suffix in SOURCE_SUFFIXES,
                    "build_name_candidate": PurePosixPath(name).name.lower() in {"makefile", "cmakelists.txt", "meson.build"}},
                "classification": classify(name, acorn, bytes(prefix), ratio)}
            if name in TEXT_MEMBERS:
                row["source_text"] = text_evidence(bytes(text))
            members.append(row)
    after = snapshot(path)
    if before != after:
        raise ValueError("Original archive changed during inspection: " + str(path))
    control = next(m for m in members if m["name"] == "RiscPkg/Control")
    lotus = [m for m in members if m["name"].startswith(LOTUS_PREFIX)]
    return {"path": str(path.resolve()), "name": path.name, "before": before, "after": after,
            "original_unchanged": True, "member_count": len(members),
            "file_count": sum(not m["is_directory"] for m in members),
            "total_uncompressed_size": sum(m["size"] for m in members),
            "lotus_tree_file_count": len(lotus), "lotus_tree_total_size": sum(m["size"] for m in lotus),
            "lotus_tree_classifications": dict(Counter(m["classification"] for m in lotus)),
            "lotus_tree_filetypes": dict(Counter(m["acorn"]["filetype_hex"] if m["acorn"] else "none" for m in lotus)),
            "lotus_tree_source_suffix_candidates": [m["name"] for m in lotus if m["source_scan"]["source_suffix_candidate"]],
            "lotus_tree_build_candidates": [m["name"] for m in lotus if m["source_scan"]["build_name_candidate"]],
            "lotus_tree_text_like_members": [m["name"] for m in lotus if m["payload_shape"]["full_ascii_printable_fraction"] >= 0.8],
            "control": parse_control(control["source_text"]["text"]), "warnings": warnings, "members": members}


def difference(a: dict, b: dict) -> dict:
    left, right = ({m["name"]: m for m in doc["members"]} for doc in (a, b))
    common = sorted(left.keys() & right.keys())
    metadata_keys = ("zip_datetime", "create_system", "flag_bits", "external_attr_hex", "central_extra_hex", "local_extra_hex")
    return {"from": a["name"], "to": b["name"], "added": sorted(right.keys() - left.keys()),
            "removed": sorted(left.keys() - right.keys()),
            "changed_payload": [n for n in common if left[n]["sha256"] != right[n]["sha256"]],
            "identical_payload_count": sum(left[n]["sha256"] == right[n]["sha256"] for n in common),
            "changed_metadata": [n for n in common if any(left[n][k] != right[n][k] for k in metadata_keys)],
            "changed_acorn_metadata": [n for n in common if left[n]["acorn"] != right[n]["acorn"]],
            "control_changes": {k: {"before": a["control"].get(k), "after": b["control"].get(k)}
                for k in sorted(a["control"].keys() | b["control"].keys()) if a["control"].get(k) != b["control"].get(k)}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "Lotus" / "zip")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("inventory.json"))
    args = parser.parse_args()
    archives = [inspect(p) for p in sorted(args.input.glob("Lotus-Turbo-Challenge-2_*.zip"))]
    if not archives:
        raise ValueError("No supplied Lotus archives found")
    report = {"schema_version": 1, "analysis": "Static read-only ZIP/RiscPkg and exact Apps/Games/!LOTUS inventory",
        "method": {"chunk_bytes": 65536, "hashes": "SHA-256 of original archives and uncompressed members",
            "member_crc": "All members read to EOF and independently compared with ZIP CRC32",
            "offsets": "Zero-based; member line offsets refer to uncompressed bytes; archive offsets refer to original ZIP bytes",
            "arc0_spec": EXTRA_SPEC, "executed": False, "extracted": False, "media_written": False,
            "ascii_shape_limit": "Printable ratios characterize bytes, not source correctness or asset semantic formats"},
        "archives": archives, "differences": [difference(a, b) for a, b in zip(archives, archives[1:])],
        "findings": [
            "Every member under exact Apps/Games/!LOTUS/ was read, hashed and inspected, including extensionless files and ARC0 metadata.",
            "Only !Run is fully printable launcher text in the Lotus application tree. No game-engine C/C++/assembly/BASIC source file or build system was found.",
            "The 0-1/0-2 !Run is source evidence for installation, decryption and compatibility patches, including inline BASIC; it is not a rebuildable game implementation.",
            "All packages label Licence: Non free and Depends: ADFFS. Copyright is a JASPP notice, not an affirmative open-source grant.",
            "0-2 changes Control only. 0-3 delegates launch to ADFBootFloppy F1023201 and removes three packaged modules; retained game payloads are unchanged.",
            "Embedded F1023201 is a gzip stream. Exact relation to original JFD disk1 and payload/protection details are independently documented in comparison.json.",
            "RISC OS filetype/load/exec metadata is preserved in ZIP ARC0 extra fields; ordinary extraction that drops it is not an equivalent guest installation.",
            "0-3 is the highest supplied package version and an ADFFS boot candidate, while 0-1/0-2 preserve visible patch scripts. Static evidence does not establish execution success on an Archimedes FPGA core."],
        "candidates": {"rebuildable_native_game_source": [], "launcher_patch_source": ["0-1:Apps/Games/!LOTUS/!Run", "0-2:Apps/Games/!LOTUS/!Run"],
            "guest_installation_candidate": "0-3 with external ADFFS and RISC OS; runtime not tested",
            "faithful_preservation_reference": "Original user-supplied JFDs, including protection/timing; ZIP game files are derivative packaging evidence"},
        "warnings": ["No execution or gameplay/fidelity validation occurred.", "No open-source or redistribution rights are inferred from archive availability.",
            "A guest package depends on RISC OS/ADFFS; it is not a standalone FPGA core or RISC-V application."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "archives": [{"name": a["name"], "members": a["member_count"],
        "lotus_tree_files": a["lotus_tree_file_count"], "sha256": a["before"]["sha256"], "original_unchanged": a["original_unchanged"]}
        for a in archives], "differences": [{k: v for k, v in d.items() if k != "changed_metadata"} | {"changed_metadata_count": len(d["changed_metadata"])} for d in report["differences"]]}, indent=2))


if __name__ == "__main__":
    main()
