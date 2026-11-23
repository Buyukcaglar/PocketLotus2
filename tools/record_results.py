"""SPDX-License-Identifier: GPL-3.0-or-later
Save compact actual results for publication, leaving logs/netlists in build.
Run only after the recorded commands finish. Never infer fit or gameplay.
"""
import hashlib
import json
import re
import csv
from datetime import datetime,timezone
from pathlib import Path
from hdl_sources import ROOT

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def quartus_evidence():
    dest=ROOT/"build/quartus"
    result=json.loads((dest/"results.json").read_text())
    for stage in result["stages"]:
        log=dest/(stage["stage"]+".log")
        if log.exists() and stage["status"] in ("passed","failed"):
            stage["log_sha256"]=sha(log)
            messages=log.read_text(errors="replace").splitlines()
            stage["critical_warnings"]=[s for s in messages if s.startswith("Critical Warning")]
            ids=re.findall(r"^(?:Critical )?Warning \((\d+)\)","\n".join(messages),re.M)
            stage["warning_counts_by_id"]={s:ids.count(s) for s in sorted(set(ids))}
    output=dest/"output_files"
    result["report_files"]=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))
        for p in sorted([*output.glob("*.rpt"),*output.glob("*.summary"),*(dest/"audit").glob("*")]) if p.is_file()]
    fit=output/"pocketlotus.fit.summary"
    if fit.exists():result["fit_summary"]=dict(line.split(" : ",1) for line in fit.read_text().splitlines() if " : " in line)
    fit_report=output/"pocketlotus.fit.rpt"
    if fit_report.exists():
        required={"a23_core","memc","vidc","ioc"}
        text=fit_report.read_text()
        rows=[]
        headers=None
        for line in text[text.index("; Fitter Resource Utilization by Entity"):].splitlines():
            fields=[x.strip() for x in line.split(";")[1:-1]]
            if fields and fields[0]=="Compilation Hierarchy Node":headers=fields
            if len(fields)>5 and fields[-2] in required:
                rows.append(dict(zip(headers,fields)))
        if len(rows)!=4:raise SystemExit("Required chipset entity missing from fitted resource report")
        result["retained_chipset_entity_resources"]=rows
    timing=output/"pocketlotus.sta.summary"
    entries=[]
    if timing.exists():
        entries=[dict(type=t,slack_ns=float(s),endpoint_tns_ns=float(n)) for t,s,n in
                 re.findall(r"Type\s+: ([^\n]+)\nSlack\s+: ([\d.-]+)\nTNS\s+: ([\d.-]+)",timing.read_text())]
    result["timing_summary"]=entries
    result["reported_timing_requirements_met"]=bool(entries) and all(e["slack_ns"]>=0 for e in entries)
    audit=[]
    for model in ("slow_85","slow_0","fast_85","fast_0"):
        entry=dict(model=model)
        for kind in ("setup","hold","recovery","removal","max_skew"):
            path=dest/"audit"/f"{model}_{kind}.rpt"
            if path.exists():
                text=path.read_text()
                match=re.search(r"Found (\d+).*?\((\d+) violated\).*?[Ww]orst case slack is ([\d.-]+)",text)
                entry[kind]=dict(reported_paths=int(match[1]),violated_paths=int(match[2]),worst_slack_ns=float(match[3])) if match else dict(no_paths_reported=True)
        checks=dest/"audit"/f"{model}_checks.rpt"
        if checks.exists():entry["constraint_checks"]={k:int(v) for k,v in re.findall(r"; (\w+)\s+; (\d+)\s+;",checks.read_text())}
        ucp=dest/"audit"/f"{model}_unconstrained.rpt"
        if ucp.exists():entry["unconstrained"]={k:dict(setup=int(s),hold=int(h)) for k,s,h in re.findall(r"; ((?:Unconstrained|Illegal) [^;]+?)\s*; (\d+)\s*; (\d+)\s*;",ucp.read_text())}
        clocks=dest/"audit"/f"{model}_clocks.tsv"
        if clocks.exists():
            with clocks.open() as stream:entry["reported_clocks"]=list(csv.DictReader(stream,delimiter="\t"))
        collections=dest/"audit"/f"{model}_collections.tsv"
        if collections.exists():
            with collections.open() as stream:entry["matched_collections"]={x["collection"]:int(x["matched_objects"]) for x in csv.DictReader(stream,delimiter="\t")}
        audit.append(entry)
    result["audit"]=audit
    result["full_board_timing_qualified"]=False
    result["remaining_timing_scope"]="APF SPI/controller/scaler/audio external delay requirements and board skew are not qualified; check reports retain unconstrained active I/O. PSRAM delays are engineering budgets, not measured board acceptance."
    result["clock_precision_note"]="TimeQuest get_clock_info periods have three decimal places; TSV frequency_mhz is approximate. Use implemented PLL ratios and nominal board reference for more precise nominal rates; oscillator tolerance/jitter are not measured."
    log=dest/"timing.log"
    ratios={}
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            m=re.search(r"create_generated_clock .*?-divide_by (\d+)(?: -multiply_by (\d+))?.*?-name \{([^}]+)\}",line)
            if m:ratios[m[3]]=dict(divide_by=int(m[1]),multiply_by=int(m[2] or 1))
        for name,data in ratios.items():
            if "FRACTIONAL_PLL" in name:data["nominal_mhz"]=74.25*data["multiply_by"]/data["divide_by"]
            else:
                prefix=name.split("|general[")[0]
                vco=next((v for k,v in ratios.items() if k.startswith(prefix+"|general[0]") and "FRACTIONAL_PLL" in k),None)
                if vco:data["nominal_mhz"]=74.25*vco["multiply_by"]/vco["divide_by"]/data["divide_by"]
    result["implemented_pll_ratios_at_nominal_74_25mhz"]=ratios
    bitstream=output/"pocketlotus.rbf"
    if bitstream.exists():result["raw_bitstream"]=dict(path=bitstream.relative_to(ROOT).as_posix(),bytes=bitstream.stat().st_size,sha256=sha(bitstream))
    result["project_sha256"]=sha(dest/"pocketlotus.qsf")
    result["constraints_sha256"]=sha(ROOT/"quartus/pocketlotus.sdc")
    return result

def main():
    results={}
    for name in ("host_reset","apf_boot","apf_run","debug","probe","memc_flyback","audio","video","serial_video","vidc_fifo","vidc_writes","psram","diagnostic","apf_elaborate"):
        stem=f"{name}-elaborate" if name=="apf_elaborate" else name
        log=ROOT/f"build/sim/{stem}.log"
        metadata=log.with_suffix(".result.json")
        if not metadata.exists():raise SystemExit(f"No completed result: {metadata}")
        entry=json.loads(metadata.read_text())
        compile_log=ROOT/f"build/sim/{name}-elaborate.log"
        if name!="apf_elaborate" and compile_log.with_suffix(".result.json").exists():
            entry["elaboration"]=json.loads(compile_log.with_suffix(".result.json").read_text())
            entry["elaboration"]["log_sha256"]=sha(compile_log)
        if name=="serial_video":
            model=next(Path(x) for x in entry["elaboration"]["command"] if x.endswith("altera_mf.v"))
            entry["intel_model"]=dict(path=str(model),sha256=sha(model),scope="Installed vendor functional DDR model; not board timing or scaler IP")
        entry["log_sha256"]=sha(log)
        entry["assertion_result"]=[line for line in log.read_text(errors="replace").splitlines() if line.startswith("PASS ") or "FATAL:" in line]
        results[name]=entry
    log=ROOT/"build/synthesis/yosys.log"
    synthesis=json.loads(log.with_suffix(".result.json").read_text())
    synthesis.update(log_sha256=sha(log),stat_sha256=sha(ROOT/"build/synthesis/stat.json"),
        generic_design=json.loads((ROOT/"build/synthesis/stat.json").read_text())["design"],
        scope="Generic unmapped synthesis; vendor RAM/DDR/PLL black boxes. Not Cyclone V utilization, fit or timing.",
        final_check=re.findall(r"Found and reported (\d+) problems\.",log.read_text())[-1]+" problems")
    netlist=json.loads((ROOT/"build/synthesis/netlist.json").read_text())["modules"]
    reached=set()
    def visit(name):
        if name in reached or name not in netlist:return
        reached.add(name)
        for cell in netlist[name]["cells"].values():visit(cell["type"])
    visit("apf_top")
    required=["a23_core","memc","ioc","vidc_audio"]
    if any(name not in reached for name in required) or not any("vidc\\CLKCPU" in name for name in reached):
        raise SystemExit("Required chipset hierarchy was discarded")
    synthesis["reachable_hierarchy"]=sorted(reached)
    verification=json.loads((ROOT/"analysis/verification.json").read_text())
    result=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),source_manifest_sha256=sha(ROOT/"source-manifest.json"),
        module_manifest_sha256=sha(ROOT/"module-manifest.json"),simulation=results,generic_synthesis=synthesis,
        quartus=quartus_evidence(),
        diagnostic=json.loads((ROOT/"build/diagnostic/manifest.json").read_text()),
        package=json.loads((ROOT/"build/package/package-manifest.json").read_text()),
        package_archive=json.loads((ROOT/"build/package/archive-sha256.json").read_text()),
        package_verification=json.loads((ROOT/"build/package/verification.json").read_text())
            if (ROOT/"build/package/verification.json").exists() else dict(status="not_run",passed=False),
        preservation=dict(passed=verification["passed"],references_clean=verification["all_materialized_reference_working_trees_clean"],
                          verification_sha256=sha(ROOT/"analysis/verification.json")),
        hardware=json.loads((ROOT/"plan/hardware-evidence.json").read_text())
            if (ROOT/"plan/hardware-evidence.json").exists() else
            dict(status="not_tested",risc_os_boot="not_tested",protected_jfd="not_tested",lotus_gameplay="not_tested"),
        next_gate="Qualify external APF/PSRAM physical timing, measured display geometry/frame rate and stereo fidelity. Next software gate: RISC OS boot with keyboard/CMOS/RTC/storage and separately identified RISC OS ROM, ADFFS and IDE-ROM dependencies; protected JFD and Lotus gameplay follow.")
    negative_log=ROOT/"build/sim/video-legacy.log"
    negative_result=negative_log.with_suffix(".result.json")
    if negative_result.exists():
        entry=json.loads(negative_result.read_text())
        entry["log_sha256"]=sha(negative_log)
        entry["assertion_result"]=[s for s in negative_log.read_text().splitlines() if "FATAL:" in s]
        entry["expected_failure_observed"]=(entry["exit_code"]==entry["expected_exit_code"]
            and any("APF blank RGB is a scaler command" in s for s in entry["assertion_result"]))
        result["video_protocol_negative_regression"]=entry
    negative_log=ROOT/"build/sim/memc_flyback-baseline.log"
    if negative_log.with_suffix(".result.json").exists():
        entry=json.loads(negative_log.with_suffix(".result.json").read_text())
        entry["log_sha256"]=sha(negative_log)
        entry["assertion_result"]=[s for s in negative_log.read_text().splitlines() if "FATAL:" in s]
        entry["expected_failure_observed"]=(entry["exit_code"]==entry["expected_exit_code"]
            and any("Flyback DMA crossed into CPU cache" in s for s in entry["assertion_result"]))
        result["memc_flyback_negative_regression"]=entry
        compile_log=ROOT/"build/sim/memc_flyback-baseline-elaborate.log"
        entry["elaboration"]=json.loads(compile_log.with_suffix(".result.json").read_text())
        entry["elaboration"]["log_sha256"]=sha(compile_log)
        entry["test_source_sha256"]=sha(ROOT/"sim/tb_memc_flyback.v")
        entry["scope"]="Directed slow-memory boundary defect; not a confirmed physical root cause"
    source_paths=[]
    for folder in ("rtl","sim","firmware","quartus","apf","tools"):
        source_paths.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    result["source_files"]=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in sorted(source_paths)]
    (ROOT/"plan/implementation-results.json").write_text(json.dumps(result,indent=2)+"\n")
    print("Recorded actual source, simulation, generic synthesis, Quartus fit/timing and package results; hardware remains separate")

if __name__=="__main__":main()
