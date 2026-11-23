# PocketLotus implementation handoff

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

Prepared on 8 October 2026. This handoff preserves the completed source and media analysis and defines the first implementation milestone. The handoff turn made documentation changes only.

## User objective and chosen architecture

Build a standalone Analogue Pocket openFPGA core that runs the supplied Acorn Archimedes version of Lotus Turbo Challenge 2. The user explicitly chose a standalone core launched from Analogue OS, rather than an application for the separate openfpgaOS RISC-V runtime.

The game is classic ARM code for an Archimedes/RISC OS environment. Start from Archie_MiSTer chipset RTL and create a Pocket APF shell. PocketRiscV and PocketDoom are references for Pocket interfaces and diagnostics; their RISC-V CPUs and native game engines do not execute Lotus directly. Preserve the original game artwork, music and behavior while adapting host interfaces and presentation.

## Required starting reads

Read any applicable live `AGENTS.md` files, then these project documents in order:

1. [Core feasibility analysis](C:/Projects/PocketLotus/analysis/POCKETLOTUS_FEASIBILITY.md).
2. [ZIP source candidate analysis](C:/Projects/PocketLotus/analysis/ZIP_SOURCE_CANDIDATES.md).
3. [Archimedes source findings](C:/Projects/PocketLotus/analysis/archimedes/findings.json).
4. [Pinned reference lock](C:/Projects/PocketLotus/analysis/reference-lock.json), [PocketRiscV findings](C:/Projects/PocketLotus/analysis/pocketriscv.json) and [Pocket game references](C:/Projects/PocketLotus/analysis/references/findings.json).
5. [Media evidence](C:/Projects/PocketLotus/analysis/media/evidence.json), [ZIP inventory](C:/Projects/PocketLotus/analysis/zip/inventory.json) and [ZIP comparison](C:/Projects/PocketLotus/analysis/zip/comparison.json).

Refresh filesystem, Git, dependency and tool availability before changing files. Use the existing analysis as the starting evidence; revisit a conclusion when implementation reveals a specific discrepancy. The current project root has no Git repository, source implementation or project `AGENTS.md`. Reference directories are separate shallow Git checkouts, some with selective source-only working trees. Avoid accidentally creating a nested repository or publishing a reference checkout.

## Pinned implementation sources

| Role | Local directory | Commit |
| --- | --- | --- |
| Chipset baseline | `references/Archimedes_MiSTer` | `7edeed510dbb80f505c1126b3a19b9416783989a` |
| Smaller-device predecessor and CPU tests | `references/Archimedes_MiSTCore` | `09ac3d0c68a16ef6524ad0a392e098bfe079fc89` |
| Pocket APF/pins/diagnostics reference | `references/PocketRiscV` | `88430e4d049e112413221433af12f3c0604f5470` |
| Pocket host peripherals reference | `references/PocketDoom` | `11cfcf96813603244ad6394f9ddc7eee36e5d9cc` |
| Optional PSRAM/DMA reference | `references/PocketQuake` | `5792fe2a0dbc4af50dbf1b64cffa0c8e3bd3c902` |

The actual MiST predecessor is `Archimedes_MiSTCore`. The similarly named `Archimedes_MiST` is an unused no-checkout clone of `mist-devel/mist-board`; its removal was rejected by automatic approval review. Leave it out of source selection. The source lock records it as unused.

Archie_MiSTer provides an Amber-derived ARM26 CPU, MEMC translation/DMA, VIDC video/sound and IOC timers/interrupts. Retain classic ARM PC/status semantics. Its MiSTer shell, HPS services, memory/PLL IP and presentation logic require Pocket replacements. The MiST predecessor targets a smaller Cyclone III EP3C25; this supports plausibility but establishes neither Pocket fit nor timing closure.

Create a module/dependency/license manifest before importing selected source into the implementation tree. Preserve file headers and pinned provenance. Amber uses LGPL-2.1-or-later; major chipset modules have BSD-style notices; the Archimedes top, FDC and IDE podule have GPL-3.0-or-later notices; the MiSTer wrapper has GPL-2.0-or-later notices. APF has its own Analogue agreement. README summaries do not replace per-file notices.

## First implementation milestone

Deliver a real Pocket Archimedes integration that can be built and exercised without proprietary RISC OS or game ROM content:

1. Establish the local implementation tree and reproducible build entry points. Initialize local Git if appropriate, retaining publication exclusions and keeping original/reference trees intact.
2. Create a Pocket Quartus project for `5CEBA4F23C8` with the real APF top, pin assignments, clock definitions and reset/loading handshake.
3. Integrate retained ARM26, MEMC, VIDC and IOC with a real Pocket external-memory adapter. Replace MiSTer HPS and board services. Keep CPU, video/sound DMA and host accesses connected with explicit arbitration and clock-domain crossings.
4. Write an original small ARM diagnostic program and suitable directed simulation that exercise memory access and peripheral behavior. Make CPU progress and memory/peripheral failures observable. A chipset held permanently in reset or disconnected may synthesize away and cannot establish resource fit.
5. Implement the necessary Pocket diagnostic video/input/audio interfaces and APF metadata/package structure. Distinguish diagnostic output from emulated Archimedes behavior. A test-pattern-only shell is an intermediate step, not completion of this milestone.
6. Run available elaboration/simulation and, with a usable Quartus installation, actual synthesis, fitting and timing analysis. Inspect retained hierarchy, utilization, constrained clock paths and memory IP. Preserve commands, reports and concrete results.

Use meaningful checks for byte/halfword/word writes, memory handshake completion, reset release, CPU/peripheral transactions and CPU/video/sound memory arbitration. PocketRiscV's external adapters currently omit CPU byte-write masks; validate or repair that contract before copying those adapters. Its active Quartus project is `src/fpga/ap_core.qsf`; the root QSF is an incomplete different project.

Keep the first milestone free of required RISC OS and RiscDev IDE ROMs. If IDE/FDC functionality is deferred, record the exact omitted interfaces and their later gate. Do not replace required hardware with unexplained stubs or label an incomplete shell playable.

Tool discovery during analysis found Python and Git on PATH, but no Quartus, Make, RISC-V compiler, Icarus or Verilator commands. WSL's launcher reported that the subsystem was not installed. This was only a PATH check. Locate installed tools or set up appropriate isolated build dependencies; continue source and simulation work that does not depend on missing proprietary tooling. Record an actual tool limitation precisely instead of inventing a successful build or repeatedly surveying the project.

## Media and ZIP facts to preserve

The immutable original JFD inputs are in `C:/Projects/PocketLotus/Lotus`:

```text
F1023201.jfd  SHA256 95b676b004f39cf0c896fe5ae1be80babbda8251d7cfb451946532e62b75915f
F1023202.jfd  SHA256 76c0f90c0853b364877e82ae7205f6ca282c6922e4a1a7dfc597e3acca9a18ce
```

Both are gzip JFDI images of ADFS E disks. Disk 1 has a data CRC-error protection sector at cylinder 79/head 1/sector 0. A plain ADF loses that behavior. The analysis ADFs under `analysis/media/F1023201` and `F1023202` also zero-fill unrepresented bytes and are not verified launch images. All timing bytes in these JFDs are unspecified; the files are not complete flux captures. Additional XLock expectations remain to be traced.

The ZIPs under `Lotus/zip` were inspected recursively in `Apps/Games/!LOTUS`:

| Package | Role | SHA-256 |
| --- | --- | --- |
| `Lotus-Turbo-Challenge-2_0-1.zip` | Historical detailed launcher | `939663a6cb92ef5b315e6aa294dafbe9fba11960e54c1ffc14c1a8b668effb93` |
| `Lotus-Turbo-Challenge-2_0-2.zip` | Same game payload; useful decryption/patch script | `64e4ff2e69a8bc804629ffbfd0334e6c3ffe2633da3b9ad0377722758d5c31fe` |
| `Lotus-Turbo-Challenge-2_0-3.zip` | Preferred packaged ADFFS runtime candidate | `cf164eed8610b4a7ea85fcf9cc5e3bfee05bc117beb549ca310a0b03daa7cca2` |

No ZIP contains rebuildable Lotus engine source. The native `Loader` is unchanged in all packages. The embedded `F1023201` is exactly the original JFD, not a protection-only stub. Version 0-3 delegates launch to `ADFBootFloppy F1023201`, omitting three bundled modules; the earlier `!Run` scripts expose loader decryption/relocation and compatibility patches. Treat those scripts as evidence, rather than silently adopting every patch as intended game behavior. All packages declare `Depends: ADFFS` and `Licence: Non free`.

The original disk loader and embedded ADFFS compatibility wrapper are separate routes. Evaluate guest RISC OS 3.11 with 4 MiB RAM and ADFFS/HDF as the first protected-JFD loading candidate. Archie's native floppy backend accepts regular ADF sectors and has no JFD parser. A direct JFD-aware FPGA backend is an alternative requiring explicit sector/error support and XLock validation.

The existing IDE podule embeds a 16 KiB RiscDev ROM. That dependency, user-provided RISC OS ROM, ADFFS files and their terms must be resolved for later guest boot work. No suitable RISC OS ROM or complete ADFFS package was provisioned in this analysis.

## Later milestones and fidelity

After hardware integration, prove guest RISC OS boot, input, CMOS and audio; then prove the exact JFD/ADFFS or native controller route; then exercise Lotus title/demo, races, controls, sound and disk transitions on Pocket.

MODE 9 is 320 by 256, 16 logical colours and nominally 50 Hz. The wrapper reserves 80 KiB of screen memory. Lotus changes palettes in relation to scanlines and IOC/VSync timing, and the original readme warns about ARM3 cache-related colour-split flicker. Preserve guest timing and palette behavior while using Pocket scaling for presentation. Cropping to 240 lines, substituting a once-per-frame palette or changing guest timing to 60 Hz requires evidence and is not an automatic adaptation.

Audio comes from Archimedes modules, music/jingle data and samples. VIDC sound/DMA/interrupt behavior still needs tracing. Doom OPL3 and Quake rendering accelerators are not replacements for the game's hardware behavior.

## Evidence and preservation rules

Keep source inspection, elaboration, simulation, synthesis, fitted timing, Pocket hardware execution, gameplay acceptance and original fidelity as distinct evidence. A package or bitstream alone does not establish a playable game.

The most recent verification checked both JFDs, all three ZIP hashes, JSON syntax and materialized reference working trees. All 579 ZIP members passed archive CRC checks during the source analysis. Recheck input hashes at implementation start with `python C:/Projects/PocketLotus/tools/verify_analysis.py`; it checks evidence consistency, not the game or core.

Preserve originals and use separate build/private working directories. The existing `.gitignore` excludes `Lotus`, private derived media, reference checkouts, ROMs and generated outputs. Keep game assets, extracted executables, ROMs and generated release content out of published source. Record source notices and dependency pins in the implementation.

Continue implementation through the first milestone instead of ending with another plan. If a genuine missing dependency blocks a particular gate, report the concrete blocker and complete independent source/build/simulation work. Update implementation status, reproducible commands, evidence and the next unfinished gate as work progresses. Public publication is a later task.
