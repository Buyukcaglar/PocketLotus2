"""SPDX-License-Identifier: GPL-3.0-or-later
Create an isolated Quartus project from the reviewed source list and pinned
Pocket QSF's pin/IO assignments. Never edit a reference checkout or write
generated Quartus outputs into the public source tree.
"""
from pathlib import Path
import json
import shutil
import hashlib
from hdl_sources import ROOT, CHIPSET, CORE
from prepare_chipset import main as prepare

SHELL = ["rtl/core_top.v", "rtl/pocket_host.v", "rtl/pocket_reset.v", "rtl/pocket_pll.v", "rtl/pocket_audio.v"]


def main():
    prepare()
    dest = ROOT / "build/quartus"
    dest.mkdir(parents=True, exist_ok=True)
    # The pinned APF datatable IP has a relative init-file name.
    (dest / "apf").mkdir(exist_ok=True)
    # Never report the reference core's build identity as PocketLotus. Fixed
    # milestone date and source digest make this independent of wall-clock time.
    identity = hashlib.sha256()
    for path in sorted(list((ROOT / "rtl").rglob("*.v")) + list((ROOT / "rtl").glob("*.vh"))):
        identity.update(path.relative_to(ROOT).as_posix().encode())
        identity.update(path.read_bytes())
    (dest / "apf/build_id.mif").write_text(
        "DEPTH=256;\nWIDTH=32;\nADDRESS_RADIX=HEX;\nDATA_RADIX=HEX;\nCONTENT BEGIN\n"
        "[00..DF] : 00000000;\nE0 : 20261008;\nE1 : 00010000;\n"
        f"E2 : {identity.hexdigest()[:8]};\n[E3..FF] : 00000000;\nEND;\n")
    assignments = []
    for line in (ROOT / "rtl/vendor/pocket/ap_core.qsf").read_text().splitlines():
        if line.startswith("set_location_assignment") or line.startswith("set_instance_assignment"):
            if "PARTITION" not in line:
                assignments.append(line)
    sources = CHIPSET + CORE + SHELL
    sources += ["rtl/vendor/pocket/apf/" + s for s in ("apf_top.v", "common.v", "io_bridge_peripheral.v",
                "io_pad_controller.v", "mf_ddio_bidir_12.v", "mf_datatable.v")]
    sources += ["rtl/vendor/pocket/core/core_bridge_cmd.v"]
    ported = {"apf_top.v", "io_pad_controller.v", "io_bridge_peripheral.v", "core_bridge_cmd.v"}
    sources = ["build/ported/" + Path(s).name if Path(s).name in ported else s for s in sources]
    qsf = [
        '# Reproduce with python tools/create_pocket_project.py',
        'set_global_assignment -name FAMILY "Cyclone V"',
        'set_global_assignment -name DEVICE 5CEBA4F23C8',
        'set_global_assignment -name TOP_LEVEL_ENTITY apf_top',
        'set_global_assignment -name ORIGINAL_QUARTUS_VERSION 25.1',
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4',
        'set_global_assignment -name SEED 1',
        # Standard Fit and performance optimization follow the pinned Archie
        # project. Keep explicit CDC/reset stages intact; no automatic retiming.
        'set_global_assignment -name FITTER_EFFORT "STANDARD FIT"',
        'set_global_assignment -name OPTIMIZATION_MODE "AGGRESSIVE PERFORMANCE"',
        'set_global_assignment -name OPTIMIZATION_TECHNIQUE SPEED',
        'set_global_assignment -name FINAL_PLACEMENT_OPTIMIZATION ALWAYS',
        'set_global_assignment -name PHYSICAL_SYNTHESIS_COMBO_LOGIC ON',
        'set_global_assignment -name PHYSICAL_SYNTHESIS_REGISTER_DUPLICATION ON',
        'set_global_assignment -name PHYSICAL_SYNTHESIS_REGISTER_RETIMING OFF',
        'set_global_assignment -name PHYSICAL_SYNTHESIS_ASYNCHRONOUS_SIGNAL_PIPELINING OFF',
        'set_global_assignment -name RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED"',
        'set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"',
        'set_global_assignment -name GENERATE_RBF_FILE ON',
        'set_global_assignment -name SEARCH_PATH "../../rtl/vendor/archie/amber"',
        'set_global_assignment -name SDC_FILE "../../quartus/pocketlotus.sdc"',
    ] + assignments
    qsf += [f'set_global_assignment -name VERILOG_FILE "../../{s}"' for s in sources]
    qsf += [
        'set_global_assignment -name MIF_FILE "apf/build_id.mif"',
    ]
    (dest / "pocketlotus.qsf").write_text("\n".join(qsf) + "\n")
    (dest / "pocketlotus.qpf").write_text('QUARTUS_VERSION = "25.1"\nPROJECT_REVISION = "pocketlotus"\n')
    (dest / "source-list.json").write_text(json.dumps(sources, indent=2) + "\n")
    print(f"Prepared {dest}: {len(sources)} source files, {len(assignments)} pinned pin/IO assignments")


if __name__ == "__main__":
    main()
