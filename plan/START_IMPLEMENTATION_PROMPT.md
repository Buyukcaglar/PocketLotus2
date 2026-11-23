# PocketLotus implementation prompt

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

```text
Work in C:\Projects\PocketLotus. Start implementing a standalone Analogue Pocket openFPGA core for the supplied Acorn Archimedes version of Lotus Turbo Challenge 2.

Read applicable AGENTS.md files and plan\IMPLEMENTATION_HANDOFF.md in full, then the feasibility, ZIP analysis and pinned source manifests it references. Use the completed analysis as your starting point and make concrete source changes.

Use Archie_MiSTer chipset RTL at 7edeed510dbb80f505c1126b3a19b9416783989a as the baseline. Retain ARM26, MEMC, VIDC and IOC; replace MiSTer host/board services with Pocket APF, clocks, pins, reset/loading and external-memory interfaces. Use PocketRiscV and PocketDoom as Pocket interface references. The target is standalone hardware; the supplied game is ARM/RISC OS code, and the ZIPs contain compiled programs/assets rather than rebuildable engine source.

Complete the first milestone: a genuine Pocket integration with a module/license manifest, reproducible 5CEBA4F23C8 Quartus project, real external-memory arbitration and an original small ARM diagnostic plus meaningful simulation. Keep the chipset connected, active and observable so synthesis cannot discard it. Produce diagnostic APF packaging and record the actual elaboration, simulation, synthesis, fitting and timing results available. A test-pattern-only shell is an intermediate step.

Locate build tools and set up appropriate isolated dependencies. Continue independent implementation when a missing tool blocks a particular check, and report the precise limitation. Preserve input files and their hashes, reference checkouts, user data and source notices. Keep copyrighted game/ROM content and generated outputs excluded from publication.

Later gates are RISC OS boot, protected JFD loading, and Lotus hardware gameplay/audio/video verification. Evaluate the 0-3 ZIP as an ADFFS runtime candidate and retain 0-2 for loader decryption/patch evidence. Preserve MODE 9's 320x256 display and nominal 50 Hz guest timing. Plain ADF conversion loses disk 1's protection behavior. Identify RISC OS, ADFFS and IDE-ROM dependencies separately.

Proceed autonomously through this first implementation milestone. Keep source, simulation, FPGA fit/timing and hardware/gameplay evidence separate. Save implementation status, exact build commands, results and the next unfinished gate in the project.
```
