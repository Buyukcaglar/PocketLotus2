"""SPDX-License-Identifier: GPL-3.0-or-later
Run real Quartus stages, recording exit codes and commands. An absent tool is
recorded as BLOCKED, never replaced with Yosys or a fabricated bitstream.
"""
import argparse
import json
import shutil
import subprocess
import time
import hashlib
from pathlib import Path
from datetime import datetime,timezone
from create_pocket_project import main as prepare
from hdl_sources import ROOT

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bin",type=Path,help="Quartus bin64 directory (with Cyclone V device support)")
    parser.add_argument("--from-stage",choices=("synthesis","fitting","assembly","timing","timing_audit"),default="synthesis",
                        help="Resume an unchanged mapped/fitted database; use synthesis after HDL changes")
    args=parser.parse_args()
    prepare()
    dest=ROOT/"build/quartus"
    executables={name: str(args.bin/f"{name}.exe") if args.bin else shutil.which(name)
                 for name in ("quartus_map","quartus_fit","quartus_asm","quartus_sta")}
    stages=[("synthesis","quartus_map",["pocketlotus","--read_settings_files=on","--write_settings_files=off"]),
            ("fitting","quartus_fit",["pocketlotus","--read_settings_files=on","--write_settings_files=off"]),
            ("assembly","quartus_asm",["pocketlotus","--read_settings_files=on","--write_settings_files=off"]),
            ("timing","quartus_sta",["pocketlotus","--do_report_timing"]),
            ("timing_audit","quartus_sta",["-t","../../tools/quartus_timing_audit.tcl"])]
    prior=dest/"results.json"
    previous=json.loads(prior.read_text()) if prior.exists() else {}
    inputs=sorted([*(ROOT/"rtl").rglob("*.v"),*(ROOT/"rtl").rglob("*.vh"),
                   *(ROOT/"build/ported").glob("*.v"),dest/"pocketlotus.qsf",dest/"apf/build_id.mif"])
    digest=hashlib.sha256()
    for path in inputs:
        digest.update(path.relative_to(ROOT).as_posix().encode());digest.update(path.read_bytes())
    source_digest=digest.hexdigest()
    if args.from_stage!="synthesis" and previous.get("mapped_source_digest") not in (None,source_digest):
        raise SystemExit("Mapped HDL/project identity changed; restart at synthesis")
    if previous:
        archive=dest/"attempts"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archive.mkdir(parents=True)
        for path in [prior,*dest.glob("*.log"),*dest.glob("output_files/*")]:
            if path.is_file():shutil.copy2(path,archive/path.name)
        if (dest/"audit").exists():shutil.copytree(dest/"audit",archive/"audit")
    results=[]
    blocked=False
    first=[stage[0] for stage in stages].index(args.from_stage)
    def save():
        result=dict(device="5CEBA4F23C8",working_directory=str(dest),stages=results,
                    mapped_source_digest=source_digest,
                    limitations="Stage success alone is not timing closure: inspect unconstrained paths, CDC, PLL frequencies, utilization and slack.")
        prior.write_text(json.dumps(result,indent=2)+"\n")
        return result
    for index,(name,exe,arguments) in enumerate(stages):
        if index<first:
            old=next((s for s in previous.get("stages",[]) if s["stage"]==name),None)
            if not old or old.get("status")!="passed":raise SystemExit(f"Cannot resume: {name} has no passing result")
            results.append(old)
            continue
        executable=executables[exe]
        if blocked or not executable or not Path(executable).is_file():
            results.append(dict(stage=name,status="not_run",reason="prior stage unavailable or failed" if blocked else f"{exe} unavailable"))
            blocked=True
            save()
            continue
        cmd=[executable,*arguments]
        start=time.monotonic()
        print(f"Running {name}",flush=True)
        results.append(dict(stage=name,status="running",command=cmd))
        save()
        with (dest/f"{name}.log").open("w") as log:
            run=subprocess.run(cmd,cwd=dest,stdout=log,stderr=subprocess.STDOUT)
        results[-1]=dict(stage=name,status="passed" if run.returncode==0 else "failed",
                        command=cmd,exit_code=run.returncode,elapsed_seconds=time.monotonic()-start)
        blocked=run.returncode!=0
        save()
    result=save()
    print(json.dumps(result,indent=2))
    return 2 if blocked else 0

if __name__=="__main__":raise SystemExit(main())
