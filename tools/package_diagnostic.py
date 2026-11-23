"""SPDX-License-Identifier: GPL-3.0-or-later
Allowlisted APF diagnostic package. Metadata-only output is explicitly marked
incomplete; --rbf requires a genuine Quartus output and performs bit reversal.
Never copies input media, reference binaries, ROMs or user data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from hdl_sources import ROOT
from build_diagnostic import assemble
from validate_apf import validate_directory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rbf", type=Path)
    args = parser.parse_args()
    validate_directory(ROOT / "apf")
    assemble()
    dest = ROOT / "build/package"
    core = dest / "Cores/PocketLotus.Diagnostic"
    assets = dest / "Assets/pocketlotusdiag/common"
    platforms = dest / "Platforms"
    for p in (core, assets, platforms):
        p.mkdir(parents=True, exist_ok=True)
    files = []
    notices=dest/"documentation"
    notices.mkdir(exist_ok=True)
    for relative in ("LICENSES/GPL-3.0.txt","LICENSES/LGPL-2.1.txt","LICENSES/README.md",
                     "source-manifest.json","module-manifest.json","docs/BUILD.md"):
        target=notices/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target);files.append(target)
    # Binary BSD notices accompany the local package verbatim. Headers in the
    # preserved HDL also include the original Analogue/Intel IP agreements.
    headers=[]
    manifest=json.loads((ROOT/"source-manifest.json").read_text())
    for source in manifest["imports"]:
        path=ROOT/source["destination"]
        if path.suffix==".v":
            text=path.read_text(encoding="utf-8")
            headers.append(source["destination"]+"\n"+text.split("module ",1)[0])
    header_path=notices/"THIRD_PARTY_NOTICES.txt"
    header_path.write_text("Verbatim leading headers of pinned HDL. Source files remain authoritative.\n\n"+"\n\n".join(headers),encoding="utf-8")
    files.append(header_path)
    if not args.rbf and (core / "bitstream.rbf_r").exists():
        raise SystemExit("Existing bitstream preserved: supply --rbf or choose a clean package directory")
    for name in ("core", "data", "video", "audio", "input", "variants", "interact"):
        json.loads((ROOT / "apf" / f"{name}.json").read_text())
        target = core / f"{name}.json"
        shutil.copyfile(ROOT / "apf" / f"{name}.json", target)
        files.append(target)
    info_target = core / "info.txt"
    shutil.copyfile(ROOT / "apf/info.txt", info_target)
    files.append(info_target)
    shutil.copyfile(ROOT / "apf/platform.json", platforms / "pocketlotusdiag.json")
    files.append(platforms / "pocketlotusdiag.json")
    shutil.copyfile(ROOT / "build/diagnostic/diagnostic.bin", assets / "diagnostic.bin")
    files.append(assets / "diagnostic.bin")
    # Auto-load instance follows PocketDoom's APF JSON asset convention.
    instance = {"instance": {"magic": "APF_VER_1", "data_slots": [{"id": 0, "filename": "diagnostic.bin"}]}}
    (assets / "diagnostic.json").write_text(json.dumps(instance, indent=2) + "\n")
    files.append(assets / "diagnostic.json")
    if args.rbf:
        data = args.rbf.read_bytes()
        if len(data) < 100000:
            raise SystemExit("RBF too small: refusing placeholder/non-bitstream packaging")
        table = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))
        (core / "bitstream.rbf_r").write_bytes(data.translate(table))
        files.append(core / "bitstream.rbf_r")
    result = dict(complete_bitstream_package=bool(args.rbf),
                  evidence="Diagnostic packaging only; no Pocket hardware result",
                  files=[dict(path=p.relative_to(dest).as_posix(), bytes=p.stat().st_size,
                              sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
    if args.rbf:
        result["raw_rbf_sha256"]=hashlib.sha256(args.rbf.read_bytes()).hexdigest()
        result["quartus_results_sha256"]=hashlib.sha256((ROOT/"build/quartus/results.json").read_bytes()).hexdigest()
        result["timing_qualification"]="Inspect plan/implementation-results.json: assembly success does not establish full board timing or Pocket acceptance"
    (dest / "package-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    (dest / "INSTALL.txt").write_text(
        "PocketLotus ARM26 diagnostic only. No RISC OS or Lotus content.\n"
        + ("Quartus bitstream included; hardware acceptance remains required.\n" if args.rbf else
           "INCOMPLETE: no FPGA bitstream is included; this package cannot launch.\n")
        + "Copy Cores, Platforms and Assets to a Pocket SD card only after a real bitstream build.\n"
        + "Version 0.1.5-diagnostic: fix outstanding video/cursor DMA at flyback; independent liveness/state probes.\n"
        + "Enable Debug Logging after power-on; run ten seconds, exit, then inspect System/Logs.\n"
        + "D1A60000..D1A60007 markers precede six coherent CPU/DMA status words and two independent probe words.\n"
        + "Probe 6 bytes LSB first: system clock, pixel clock, CPU ACK, video ACK edge observations modulo 256.\n"
        + "Probe 7 bytes LSB first: sound ACK, peripheral ACK edge observations, memory/reset flags low/high.\n"
        + "Probe flags are individually synchronized, not a coherent state during transitions; inspect stable stalls.\n"
        + "Merge Cores, Platforms and Assets from this archive into the SD root, replacing this core's files.\n"
        + "Select ARM diagnostic / diagnostic.bin when the asset picker opens.\n"
        + "Expected: VIDC 320x256 diagnostic stripes, status 0x600d00xx, active DMA.\n"
        + "Bridge status at F0000000..F0000014: result, CPU, video, sound, peripheral count, last CPU address.\n"
        + "GPIO user1 flags 0xbad0; dbg_tx exposes CPU transaction counter bit 10.\n"
        + "RISC OS boot, protected JFD and Lotus gameplay/audio/video are later gates.\n")
    # Deterministic explicit allowlist: fixed archive time, no directory sweep.
    archive=dest/"PocketLotus.Diagnostic.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted([*files,dest/"INSTALL.txt",dest/"package-manifest.json"]):
            info=zipfile.ZipInfo(path.relative_to(dest).as_posix(),date_time=(2026,10,8,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,path.read_bytes())
    (dest/"archive-sha256.json").write_text(json.dumps(dict(path=archive.name,bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest()),indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
