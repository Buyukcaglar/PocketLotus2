"""Import selected, hash-locked HDL without modifying reference checkouts.

The manifest is written BEFORE copying any source. Repeat runs verify imported
bytes; local modifications are never silently overwritten.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "Archimedes_MiSTer": "7edeed510dbb80f505c1126b3a19b9416783989a",
    "PocketRiscV": "88430e4d049e112413221433af12f3c0604f5470",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for repo, commit in SOURCES.items():
        ref = ROOT / "references" / repo
        actual = subprocess.check_output(["git", "-C", str(ref), "rev-parse", "HEAD"], text=True).strip()
        if actual != commit:
            raise SystemExit(f"Wrong reference HEAD: {repo}: {actual}")
        if repo == "Archimedes_MiSTer":
            paths = list((ref / "rtl/amber").glob("*.v"))
            paths += list((ref / "rtl/vidc").glob("*.v"))
            paths += [ref / "rtl" / name for name in ("memc.v", "memc_translator.v", "ioc.v", "ioc_irq.v", "latches.v")]
        else:
            paths = [p for p in (ref / "src/fpga/apf").iterdir() if p.suffix in (".v", ".qip", ".mif")]
            paths += [ref / "src/fpga/core/core_bridge_cmd.v", ref / "src/fpga/ap_core.qsf"]
        for path in sorted(paths):
            source = path.relative_to(ref).as_posix()
            if repo == "Archimedes_MiSTer":
                dest = "rtl/vendor/archie/" + source.removeprefix("rtl/")
                license_id = "LGPL-2.1-or-later" if "/amber/" in "/" + source else "BSD-3-Clause (per-file notice)"
            else:
                dest = "rtl/vendor/pocket/" + source.removeprefix("src/fpga/")
                license_id = "Analogue APF agreement; embedded Intel IP notices where present"
            entries.append(dict(repository=repo, commit=commit, source=source, destination=dest,
                                sha256=sha(path), notice=license_id))
    manifest = {
        "schema": 1, "imports": entries,
        "original_code": "GPL-3.0-or-later; see LICENSES/README.md",
        "excluded": [
            "MiSTer HPS/sys shell, PLL and SDRAM board IP",
            "FDC/IDE podule and RiscDev IDE ROM: no disk services in diagnostic target",
            "RISC OS ROM, ADFFS, Lotus programs/assets and all derived game media",
            "PocketRiscV CPU/firmware, game engines and unneeded accelerators"],
        "reference_only": {"PocketDoom": "11cfcf96813603244ad6394f9ddc7eee36e5d9cc",
                           "Archimedes_MiSTCore": "09ac3d0c68a16ef6524ad0a392e098bfe079fc89"},
    }
    out = ROOT / "source-manifest.json"
    if out.exists() and json.loads(out.read_text()) != manifest:
        raise SystemExit("Manifest differs; review source selection before reimport")
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    for item in entries:
        dest = ROOT / item["destination"]
        if dest.exists():
            if sha(dest) != item["sha256"]:
                raise SystemExit(f"Locally modified import: {dest}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "references" / item["repository"] / item["source"], dest)
    print(f"Verified/imported {len(entries)} files; references unchanged")


if __name__ == "__main__":
    main()
