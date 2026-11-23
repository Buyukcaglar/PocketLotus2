"""SPDX-License-Identifier: GPL-3.0-or-later
Reproducible Icarus elaboration/simulation with isolated OSS CAD Suite.
"""
import argparse
import os
from pathlib import Path
import subprocess
import time
import json
from hdl_sources import ROOT, CHIPSET, CORE
from prepare_chipset import main as prepare


def run(cmd, log, env, expected_exit=0):
    print(" ".join(str(s) for s in cmd), flush=True)
    start = time.monotonic()
    if log.with_suffix(".result.json").exists():
        log.with_suffix(".result.json").unlink() # this runner's stale result only
    with log.open("w") as f:
        result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
    elapsed=time.monotonic()-start
    log.with_suffix(".result.json").write_text(json.dumps(dict(command=[str(s) for s in cmd],
        working_directory=str(ROOT),exit_code=result.returncode,elapsed_seconds=elapsed,
        expected_exit_code=expected_exit),indent=2)+"\n")
    print(f"exit={result.returncode} elapsed={elapsed:.2f}s log={log}", flush=True)
    if result.returncode!=expected_exit:
        print(log.read_text(errors="replace")[-12000:])
        raise SystemExit(result.returncode)


def main():
    prepare()
    from build_diagnostic import assemble
    assemble()
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default=str(ROOT / "build/deps/oss-cad-suite"))
    parser.add_argument("--test", default="diagnostic")
    parser.add_argument("--quartus-simlib", default="C:/altera_lite/25.1std/quartus/eda/sim_lib")
    parser.add_argument("--legacy-memc-flyback", action="store_true", help="Expected-failure regression with the original MEMC abort path")
    args = parser.parse_args()
    suite = Path(args.suite)
    env = dict(os.environ)
    env["PATH"] = str(suite / "bin") + os.pathsep + str(suite / "lib") + os.pathsep + env["PATH"]
    dest = ROOT / "build/sim"
    dest.mkdir(parents=True, exist_ok=True)
    test = args.test
    if args.legacy_memc_flyback and test!="memc_flyback":
        parser.error("--legacy-memc-flyback requires --test memc_flyback")
    stem = test+"-baseline" if args.legacy_memc_flyback else test
    if test == "serial_video":
        files=["rtl/pocket_video.v","rtl/vendor/pocket/apf/mf_ddio_bidir_12.v",
            str(Path(args.quartus_simlib)/"altera_mf.v"),"sim/tb_serial_video.v"]
        top="tb_serial_video"
    elif test in ("apf_elaborate", "apf_boot", "apf_run", "debug"):
        from create_pocket_project import main as project
        import json
        project()
        files = json.loads((ROOT / "build/quartus/source-list.json").read_text()) + ["sim/primitive_models.v"]
        top = "apf_top" if test == "apf_elaborate" else "tb_apf_boot" if test=="apf_run" else f"tb_{test}"
        if test in ("apf_boot","apf_run"):
            files += ["sim/psram_model.v", "sim/tb_apf_boot.v"]
        elif test == "debug":
            files += ["sim/tb_debug.v"]
    else:
        files = CHIPSET + CORE + ["rtl/pocket_host.v", "rtl/pocket_reset.v", "rtl/pocket_audio.v",
                                 "sim/primitive_models.v", "sim/psram_model.v", f"sim/tb_{test}.v"]
        top = f"tb_{test}"
    run([str(suite / "bin/iverilog.exe"), "-g2012", "-DSIMULATION", *(["-DLONG_APF_DIAGNOSTIC"] if test=="apf_run" else []), *(["-DLEGACY_MEMC_FLYBACK"] if args.legacy_memc_flyback else []), "-I", "rtl/vendor/archie/amber", "-I", "build/diagnostic", "-s", top,
         "-o", str(dest / f"{stem}.vvp"), *files], dest / f"{stem}-elaborate.log", env)
    if test == "apf_elaborate":
        return
    run([str(suite / "bin/vvp.exe"), "-i", str(dest / f"{stem}.vvp")], dest / f"{stem}.log", env, expected_exit=1 if args.legacy_memc_flyback else 0)
    print((dest / f"{stem}.log").read_text(errors="replace")[-2000:])


if __name__ == "__main__":
    main()
