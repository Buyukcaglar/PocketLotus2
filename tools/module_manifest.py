"""SPDX-License-Identifier: GPL-3.0-or-later
Inventory actual selected modules, dependencies, hashes and source notices.
Generated derivatives are represented by their preserved original and the
checked-in transformation tool/body. This manifest is source evidence only.
"""
import hashlib
import json
import re
from pathlib import Path
from hdl_sources import ROOT
from create_pocket_project import main as prepare

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    prepare()
    imports={x["destination"]:x for x in json.loads((ROOT/"source-manifest.json").read_text())["imports"]}
    paths=json.loads((ROOT/"build/quartus/source-list.json").read_text())
    modules=[]
    for selected in paths:
        path=ROOT/selected
        text=path.read_text(encoding="utf-8")
        origin=selected
        if selected.startswith("build/ported/"):
            name=Path(selected).name
            origin=next(x for x in imports if Path(x).name==name)
        provenance=imports.get(origin)
        for name in re.findall(r"^\s*module\s+(\w+)",text,re.M):
            entry=dict(module=name,selected_file=selected,sha256=sha(path),preserved_source=origin,
                       license=provenance["notice"] if provenance else "GPL-3.0-or-later")
            if provenance:
                entry.update(repository=provenance["repository"],commit=provenance["commit"],
                             original_sha256=provenance["sha256"])
                if name in ("sram_byte_en","sram_line_en"):
                    entry["notice_detail"]="No license header in this file; Amber directory provenance is LGPL, not a newly added per-file upstream notice. Audit before distribution."
            if selected!=origin:
                entry["transform"]="tools/prepare_chipset.py"
                if name=="vidc_fifo":entry["replacement_body"]="rtl/vidc_fifo_body.vh"
            modules.append(entry)
    names={x["module"] for x in modules}|{"altsyncram","altddio_bidir","altera_pll"}
    for entry in modules:
        text=(ROOT/entry["selected_file"]).read_text(encoding="utf-8")
        entry["dependencies"]=sorted(name for name in names if re.search(
            r"^\s*"+re.escape(name)+r"\s*(?:#\s*\([\s\S]*?\)\s*)?\w+\s*\(",text,re.M))
    result=dict(schema=1,top="apf_top",device="5CEBA4F23C8",modules=modules,
        external_primitives=["altsyncram (Amber cache and APF datatable)","altddio_bidir (APF scaler)","altera_pll (two independent PLLs)"],
        source_manifest="source-manifest.json",
        excluded=["MiSTer HPS/sys/SDRAM/PLL shell","FDC and IDE podule/IDE ROM","RISC OS ROM/ADFFS/Lotus content"],
        transformations_sha256=sha(ROOT/"tools/prepare_chipset.py"),
        reference_interfaces={"PocketRiscV":"88430e4d049e112413221433af12f3c0604f5470","PocketDoom":"11cfcf96813603244ad6394f9ddc7eee36e5d9cc"})
    (ROOT/"module-manifest.json").write_text(json.dumps(result,indent=2)+"\n")
    print(f"Recorded {len(modules)} selected modules and primitive dependencies")

if __name__=="__main__":main()
