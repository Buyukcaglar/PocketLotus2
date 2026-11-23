"""SPDX-License-Identifier: GPL-3.0-or-later
Install only the verified diagnostic package's twelve SD files; read back hashes.
No SD backup, directory sweep, deletion, or changes to other cores/user data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from hdl_sources import ROOT
from verify_package import main as verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True,help="Mounted Pocket SD root")
    args=parser.parse_args()
    sd=args.root.resolve(strict=True)
    if not sd.is_dir():
        raise SystemExit("SD root is not a directory")
    verify()
    package=ROOT/"build/package"
    core="Cores/PocketLotus.Diagnostic/"
    allowed={core+name for name in ("core.json","data.json","video.json","audio.json",
        "input.json","variants.json","interact.json","info.txt","bitstream.rbf_r")}
    allowed.update(("Platforms/pocketlotusdiag.json",
        "Assets/pocketlotusdiag/common/diagnostic.bin",
        "Assets/pocketlotusdiag/common/diagnostic.json"))
    manifest=json.loads((package/"package-manifest.json").read_text())
    files={item["path"]:item for item in manifest["files"] if item["path"] in allowed}
    if set(files)!=allowed:
        raise SystemExit("Diagnostic installation allowlist is incomplete")
    destinations={name:(sd/name).resolve() for name in allowed}
    if any(not path.is_relative_to(sd) for path in destinations.values()):
        raise SystemExit("Installation destination escapes SD root")
    changes=[]
    for name in sorted(allowed):
        destination=destinations[name]
        previous=sha(destination) if destination.is_file() else None
        if previous!=files[name]["sha256"]:
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(package/name,destination)
            changes.append(dict(path=str(destination),previous_sha256=previous,
                sha256=sha(destination)))
    readback=[dict(path=str(destinations[name]),sha256=sha(destinations[name]),
        matches_package=sha(destinations[name])==files[name]["sha256"]) for name in sorted(allowed)]
    report=dict(version=json.loads((package/core/"core.json").read_text())["core"]["metadata"]["version"],
        command=["python","tools/install_diagnostic.py","--root",str(sd)],
        working_directory=str(ROOT),changes=changes,files=readback,
        all_matched=all(item["matches_package"] for item in readback),
        scope="SD file installation/readback only; no hardware execution claim")
    (package/"sd-installation.json").write_text(json.dumps(report,indent=2)+"\n")
    if not report["all_matched"]:
        raise SystemExit("SD readback mismatch; see sd-installation.json")
    print(f"Installed {report['version']}: {len(changes)} changed files, all twelve hashes verified on {sd}")


if __name__=="__main__":
    main()
