"""SPDX-License-Identifier: GPL-3.0-or-later
Optional generic Yosys synthesis of the complete APF top. Vendor PLL, DDR and
RAM primitives remain black boxes: this is source/hierarchy evidence only,
not a Cyclone V fit or TimeQuest result.
"""
import json
import os
import re
from pathlib import Path
from hdl_sources import ROOT
from create_pocket_project import main as prepare
from simulate import run


def main():
    prepare()
    out = ROOT / "build/synthesis"
    out.mkdir(parents=True, exist_ok=True)
    text = (ROOT / "sim/primitive_models.v").read_text()
    models = []
    for name in ("altsyncram", "altddio_bidir"):
        start = text.index("module " + name)
        end = text.index(");", start) + 2
        models.append("(* blackbox *) " + text[start:end] + "\nendmodule\n")
    models.append('''(* blackbox *) module altera_pll #(
        parameter fractional_vco_multiplier="true",reference_clock_frequency="74.25 MHz",
        parameter operation_mode="normal",number_of_clocks=4,
        parameter output_clock_frequency0="42.0 MHz",phase_shift0="0 ps",duty_cycle0=50,
        parameter output_clock_frequency1="8.0 MHz",phase_shift1="0 ps",duty_cycle1=50,
        parameter output_clock_frequency2="8.0 MHz",phase_shift2="31250 ps",duty_cycle2=50,
        parameter output_clock_frequency3="12.288 MHz",phase_shift3="0 ps",duty_cycle3=50,
        parameter pll_type="General",pll_subtype="General"
    )(input refclk,rst,fbclk,output [number_of_clocks-1:0] outclk,output locked,fboutclk);
    endmodule
    ''')
    (out / "ip.v").write_text("\n".join(models))
    sources = json.loads((ROOT / "build/quartus/source-list.json").read_text())
    script = ["read_verilog -lib build/synthesis/ip.v"]
    script += [f'read_verilog -sv -defer -Irtl/vendor/archie/amber "{s}"' for s in sources]
    script += [
        "hierarchy -check -top apf_top", "synth -top apf_top -noabc", "check -assert",
        "tee -o build/synthesis/stat.json stat -json",
        "write_json build/synthesis/netlist.json", "write_verilog build/synthesis/netlist.v",
    ]
    (out / "synth.ys").write_text("\n".join(script) + "\n")
    suite = ROOT / "build/deps/oss-cad-suite"
    env = dict(os.environ)
    env["PATH"] = str(suite / "bin") + os.pathsep + str(suite / "lib") + os.pathsep + env["PATH"]
    run([str(suite / "bin/yosys.exe"), "-s", "build/synthesis/synth.ys"], out / "yosys.log", env)
    print((out / "yosys.log").read_text(errors="replace")[-2000:])


if __name__ == "__main__":
    main()
