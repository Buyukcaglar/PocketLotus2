# Reproducible commands

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

Run from `C:\Projects\PocketLotus` in PowerShell with Python 3 and Git. No system
PATH or reference checkout changes are needed. All generated files are in
ignored `build`; `rtl/vendor` contains preserved hash-locked source.

```powershell
Set-Location C:\Projects\PocketLotus
python tools/verify_analysis.py
python tools/import_sources.py
python tools/bootstrap_sim.py
python tools/build_diagnostic.py
python tools/create_pocket_project.py
python tools/module_manifest.py
python tools/simulate.py --test apf_elaborate
python tools/simulate.py --test host_reset
python tools/simulate.py --test apf_boot
python tools/simulate.py --test apf_run
python tools/simulate.py --test debug
python tools/simulate.py --test audio
python tools/simulate.py --test video
python tools/simulate.py --test serial_video
python tools/simulate.py --test vidc_fifo
python tools/simulate.py --test vidc_writes
python tools/simulate.py --test psram
python tools/simulate.py --test diagnostic
python tools/synthesize.py
python tools/package_diagnostic.py
```

The pinned Windows OSS CAD Suite is `2026-10-08`, SHA-256
`86dea50f6de7dc193d6760e01f3e4317021b68097271c3555b613c16caaafb0a`.
The bootstrap verifies the 601,728,860-byte archive before extracting it to
`build/deps/oss-cad-suite`, preserving any existing installation. Icarus and
Yosys subprocesses receive both suite `bin` and `lib` on their local PATH.
The restricted ARM assembler needs no cross-compiler. Each runner saves exact
expanded commands, working directory, exit code and elapsed time beside its
log as `.result.json`. The full diagnostic takes several minutes of wall time;
the guest simulation stays live with a one-millisecond progress watchdog.

The generated Quartus project is `build/quartus/pocketlotus.qpf`, revision
`pocketlotus`, top `apf_top`, part `5CEBA4F23C8`, seed 1. It selects 42 Verilog
files and 589 unchanged location/instance pin and I/O assignments from the
pinned active PocketRiscV QSF. It regenerates bounded source derivatives and a
deterministic PocketLotus build identity instead of reusing the reference ID.
The generator never writes into a reference checkout.

With Quartus Prime Lite 25.1 and Cyclone V device support installed:

```powershell
python tools/build_quartus.py --bin C:\altera_lite\25.1std\quartus\bin64
```

This is the user-installed path verified in this session. The wrapper runs these
stages in `build/quartus` and stops dependent stages on failure/unavailability:

```powershell
quartus_map pocketlotus --read_settings_files=on --write_settings_files=off
quartus_fit pocketlotus --read_settings_files=on --write_settings_files=off
quartus_asm pocketlotus --read_settings_files=on --write_settings_files=off
quartus_sta pocketlotus --do_report_timing
quartus_sta -t ../../tools/quartus_timing_audit.tcl
```

Inspect the generated reports: real part, retained ARM/MEMC/VIDC/IOC hierarchy,
ALM/register/M10K/PLL use, achieved clock frequency/phase, fit success, setup/hold
and recovery/removal slack, unconstrained paths and matched CDC/multicycle
collections. Complete APF/scaler board timing constraints and validate PSRAM
budgets. A zero process exit is not by itself timing closure. The installed
tool is `25.1std.0 Build 1129 10/21/2025 SC Lite Edition`. Actual vendor reports
and the assembled RBF are retained under `build/quartus/output_files`; consult
`plan/implementation-results.json` and `plan/IMPLEMENTATION_STATUS.md` for the
final run and remaining qualification limits.

The project uses Standard Fit, aggressive performance and seed 1. Automatic
register retiming and asynchronous pipelining are disabled to preserve the
explicit CDC/reset chains. The audit retains slow/fast 1100 mV models at 0°C
and 85°C, clock periods/ratios, setup/hold/recovery/removal, Gray skew,
collection counts and unconstrained I/O. External APF SPI/controller, video
scaler and audio delay requirements remain a board qualification gate.
Inactive constant pins also appear in the raw missing-output-delay report;
the unconstrained-path report identifies the active paths separately.

Completed attempts are copied under `build/quartus/attempts` before rebuilding.
`--from-stage fitting`, `assembly`, `timing` or `timing_audit` resumes an
unchanged mapped source/project; restart at synthesis after HDL changes.
Completed stage records and hashes are saved, including unsuccessful attempts.

Generic Yosys synthesis retains vendor PLL/RAM/DDR primitives as black boxes.
Its cell count is not Cyclone V ALM utilization, memory-IP validation, fitting,
or timing. Simulation uses functional models and ideal requested clocks; it
cannot establish physical clock jitter, pin behavior or hardware acceptance.

After a successful real Quartus assembly:

```powershell
python tools/package_diagnostic.py --rbf build/quartus/output_files/pocketlotus.rbf
python tools/verify_package.py
```

Packaging uses an explicit allowlist and reverses RBF bits for APF. Without
`--rbf` it generates diagnostic metadata, the original ARM binary and an
explicitly **incomplete** package in `build/package`; it cannot launch. The
size check rejects tiny placeholders but does not authenticate arbitrary
bitstreams: use only the successful build's output and inspect its provenance.
Use the package for diagnostic hardware testing; acceptance requires observed
Pocket behavior.

Both packaging and verification validate the diagnostic metadata profile
against Analogue's documented field/count/length limits. Run
`python tools/validate_apf.py` independently before rebuilding. This is a
bounded schema check, not execution of the firmware's parser. Version
0.1.1-diagnostic fixes the first package's host 0082 rejection and oversized
labels; see `plan/SETUP_FAILURE.md` for the reproduced regression and the
user-reported OS 2.7 launch failure. Replacement hardware acceptance is pending.
Version 0.1.2-diagnostic additionally fixes the metadata/directory identity
mismatch confirmed in the device boot log and includes the About info.txt.
Its bitstream is identical to the rebuilt 0.1.1 bitstream; no new RTL build is
claimed. Validation now enforces the installed `author.shortname` directory
and verification checks the About version against core metadata.
Version 0.1.3-diagnostic adds a real VIDC-to-APF video adapter: single-cycle
sync events, separated frame/line events and zero RGB during blanking. Its
directed receiver test and complete chipset test check these contracts.
The old direct output fails the blanking assertion. This version requires
the recorded new Quartus synthesis/fit/assembly/timing run.

Version 0.1.3 loaded on Pocket but the user reported a white bar/tone followed
by brief coloured stripes that disappeared. Its device trace confirms successful
setup/loading/reset exit and contains no internal chipset status. Version
0.1.4 adds APF target command `0152 Debug Event Log` without guest memory access
or CPU stalls. Enable Debug Logging after power-on, run ten seconds, exit the
core and inspect `System/Logs`. Every nominal half-second, six coherent words
are emitted as marker/data pairs: `D1A60000` result, `D1A60001` CPU count,
`D1A60002` video count, `D1A60003` sound count, `D1A60004` peripheral count,
`D1A60005` last CPU address. Logging shares the target FSM, waits for each host
result, gives Ready to Run priority and cancels a pending event on guest reset.

Version 0.1.4's physical trace contained 33 identical snapshots over 16 seconds.
Version 0.1.5 adds two independent bridge-domain probe words, bypassing that
mailbox. `D1A60006` bytes from least significant to most significant contain
system-clock, pixel-clock, CPU-ACK and video-ACK edge observations. `D1A60007`
contains sound-ACK and peripheral-ACK observations in the low two bytes, then
16 flags: bit 15 PLL locked, 14 CPU reset, 13 pixel reset, 12 ready, 11 MEMC cyc,
10 MEMC stb, 9 MEMC write, 8 memory ACK, 7 PSRAM busy, 6 arbiter armed,
5:3 arbiter state, 2:0 PSRAM state. State values are defined in the RTL.
The observations wrap modulo 256 and count divided-clock/count-bit transitions,
not transactions. System clock division is 2^17 and pixel clock division 2^14
per transition. All probes use two capture stages. Individually synchronized
flags describe a stable stall; they are not a coherent bus during transitions.

```powershell
python tools/simulate.py --test probe
python tools/simulate.py --test memc_flyback
python tools/simulate.py --test memc_flyback --legacy-memc-flyback
python tools/inspect_runtime_log.py build/hardware-logs/<log>.txt --words 8 --output build/hardware-logs/<analysis>.json
```

Use `--words 6` for 0.1.4. The parser retains incomplete bursts and unexpected
markers alongside the unchanged original log and its SHA-256. Frozen exported
values alone do not prove stopped clocks or identify a memory fault.

The flyback regression uses real MEMC, arbiter and PSRAM pins at sixteen
video/cursor physical-read and acknowledgement boundaries. The corrected
derivative drains its accepted DMA burst before resetting pointers, prevents
new video/cursor grants in flyback, and then returns the CPU's own miss/hit
data. The legacy option defines `LEGACY_MEMC_FLYBACK` for simulation only and
expects the simulator to exit 1 with DMA data entering the CPU cache. The
runner accepts that expected failure and records both exit codes and commands.
Quartus does not define the legacy switch. This is a proven source/simulation
defect; the physical trace does not by itself establish the same root cause.

`serial_video` uses the installed Intel `altera_mf.v` model and the actual
pinned APF DDR wrappers. Change its location with `--quartus-simlib <directory>`.
It verifies three synthetic guest frames at the decoded DDR pins. `apf_run`
performs APF load/reload through the real command handler and runs ARM/DMA,
services debug events and checks sustained serialized frames. Only that test's
logging interval is accelerated from half a second to ten milliseconds. The
functional DDR model now captures both halves at the rising edge as Intel's
model does. These checks cover protocol/alignment, not scaler implementation,
electrical delays or board acceptance. Exact commands and Intel model hash are
recorded separately from hardware observations.

The deterministic `build/package/PocketLotus.Diagnostic.zip` includes the
allowlisted APF directories, original ARM diagnostic, manifest and source
notices. `archive-sha256.json` records its checksum. No game, RISC OS, ADFFS or
IDE-ROM bytes are included. Copying the diagnostic to a Pocket is a separate
hardware acceptance run; the archive itself is not evidence of one.

For the user's mounted Pocket SD at `F:\`, direct installation and readback are
reproducible with `python tools/install_diagnostic.py --root F:\`. This verifies
the completed package, copies only changed files from a twelve-file diagnostic
allowlist, and checks all twelve installed hashes. It makes no SD backup and
does not change other cores, saves or settings. The result and exact command
are saved to `build/package/sd-installation.json`; it is file evidence only.

After the commands finish, `python tools/record_results.py` refreshes the
compact checked-in evidence from actual log/result files. Do not run it during
an unfinished simulation or replace evidence with expectations.

The original JFDs, ZIP/extracted content, reference repositories, ROMs, private
data, and generated files stay excluded by `.gitignore`. No source publication
or release upload has been performed. Per-file notices and the two Amber SRAM
wrappers' missing headers need distribution review before a source release.
