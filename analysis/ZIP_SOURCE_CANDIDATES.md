# Lotus ZIP source candidate analysis

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md). The package comparison remains valid; the conclusion that a native route is out of reach does not.

None of the three ZIPs contains a rebuildable Lotus game engine. The `Apps/Games/!LOTUS` trees contain compiled ARM programs, game assets, launcher scripts and the protected disk 1 JFD image. For the standalone Archimedes FPGA route, `Lotus-Turbo-Challenge-2_0-3.zip` is the preferred packaged runtime candidate to investigate. For loader reverse engineering, the longer script in 0-2 is useful; it is identical to the script in 0-1.

This selection concerns the supplied local versions. It does not establish that a package runs on the future Pocket core.

## Package comparison

| Archive | Bytes | ZIP members | What changes | Appropriate use |
| --- | ---: | ---: | --- | --- |
| Lotus-Turbo-Challenge-2_0-1.zip | 1,831,076 | 194 | Initial package with a detailed compatibility launcher | Historical boot and loader evidence |
| Lotus-Turbo-Challenge-2_0-2.zip | 1,831,087 | 194 | Only `RiscPkg/Control` changes: version and `Environment: arm` | Same game payload; clearer architecture metadata and detailed launcher |
| Lotus-Turbo-Challenge-2_0-3.zip | 1,819,799 | 191 | Removes `JoyMod`, `MemMod`, `MusMod2`; replaces `!Run` with `ADFBootFloppy F1023201` | Preferred ADFFS package candidate for a guest hard disk |

Every retained game/resource member has the same bytes across versions. The 0-1 to 0-2 update does not change the loader, music, graphics or game logic. The 0-3 changes concern launching and removal of bundled modules, rather than a replacement game engine.

All three `RiscPkg/Control` files declare `Depends: ADFFS` and `Licence: Non free`. The 0-2 and 0-3 controls explicitly specify `Environment: arm`. The copyright notice describes JASPP's distribution process; it does not provide this project with an open source license for the game.

## Contents of Apps Games LOTUS

The archives include `Loader`, `WimpBanner`, graphics, music/jingles, `SampleD`, resource files under `DISK1` and `DISK2`, sprites, metadata and boot instructions. The recursive scan includes extensionless files and RISC OS file attributes. No complete game C/C++ source, assembly source tree, engine build scripts or rebuildable project was identified. RISC OS metadata and binary signatures distinguish the executable files from readable scripts.

The application subtree has 192 files in 0-1/0-2 and 189 in 0-3. Each contains 184 binary resource/data files, two absolute ARM executables (`Loader` and `WimpBanner`), one sprite resource, one gzip JFD and the readable `!Run`; the earlier versions also contain the three compiled modules. Across the complete archives, all 579 members passed ZIP CRC checks.

Relative to the original JFD filesystem, 0-1 and 0-2 each have 190 exact original application-file matches, a replacement `!Run`, and no omissions from the original application. Version 0-3 has 187 exact matches, the replacement `!Run`, and the three omitted modules above. The `Loader` bytes match the original disk in all versions; its SHA-256 is `10d14e0d2bb8c8ed7edd5097943c94b25d5b18846186e26427570372a4a54711`.

The detailed 2,494-byte `!Run` in 0-1 and 0-2 is readable source for launching and patching the existing binary. It loads and decrypts the ARM loader, moves code to a specified address, applies compatibility changes, conditionally invokes ARM3 JIT support and starts the resulting program. It includes a small BASIC decryption loop and explicit instruction patch addresses. These are valuable reverse-engineering clues, but they do not supply the game implementation needed to compile a native RISC-V port.

The 0-3 launcher is just 22 bytes: `ADFBootFloppy F1023201`. It delegates to ADFFS and the disk's embedded boot wrapper. The separate game files remain in the ZIP, but their presence does not prove that this particular launch path reads those copies rather than the mounted JFD. That distinction needs runtime tracing.

## Effect on the Pocket core plan

The packages confirm that the ADFFS guest route is an existing packaging approach, rather than a newly invented loading scheme. Investigate 0-3 inside a guest RISC OS environment with the required ADFFS components and 4 MiB guest RAM. Preserve RISC OS file type/load/execute metadata when constructing a guest hard disk; copying names and bytes through a host filesystem alone may lose the attributes needed for launching.

The embedded `F1023201` is byte-identical to the supplied 599,729-byte original JFD across all packages, with SHA-256 `95b676b004f39cf0c896fe5ae1be80babbda8251d7cfb451946532e62b75915f`. It has the same protected CRC-error sector and 1,427-byte embedded Obey wrapper. Its error behavior must still be supplied by ADFFS or a future native floppy backend. The short launcher does not convert that disk to a plain ADF or eliminate the ARM/RISC OS dependency.

The earlier long launcher explicitly patches command-line/CRC checks in the relocated loader. Treat that as a distinct historical compatibility route and record any future use of those patches.

The source candidates by purpose are:

| Purpose | Selection |
| --- | --- |
| Rebuild the whole game as native RISC-V firmware | None of these ZIPs qualifies |
| Supply a packaged runtime to the proposed standalone ARM core | Investigate 0-3 with user-provided RISC OS and ADFFS |
| Trace loader decryption and compatibility patches | Use the 0-2 launcher, equivalent to 0-1 |
| Preserve original media and compare behavior | Retain both original JFD images and their hashes |

The recommended architecture remains an Archie chipset port inside a Pocket APF shell. These ZIPs improve the available boot and reverse-engineering evidence; they do not replace ARM26, MEMC, VIDC, IOC or the guest OS with a native game engine.

## Integrity and reproducibility

Original archive SHA-256 hashes:

```text
0-1  939663a6cb92ef5b315e6aa294dafbe9fba11960e54c1ffc14c1a8b668effb93
0-2  64e4ff2e69a8bc804629ffbfd0334e6c3ffe2633da3b9ad0377722758d5c31fe
0-3  cf164eed8610b4a7ea85fcf9cc5e3bfee05bc117beb549ca310a0b03daa7cca2
```

The [ZIP inventory](C:/Projects/PocketLotus/analysis/zip/inventory.json) records member hashes, metadata and content classification. The [JFD comparison](C:/Projects/PocketLotus/analysis/zip/comparison.json) records overlap with the original disk files. Reproduce the inspection with [inspect_zips.py](C:/Projects/PocketLotus/analysis/zip/inspect_zips.py) and [compare_zip_payloads.py](C:/Projects/PocketLotus/analysis/zip/compare_zip_payloads.py).

The ZIPs and JFDs remain unchanged. No launcher, extracted program, emulator or FPGA was executed. Game content stays local and excluded from publication. Read [the complete core feasibility analysis](C:/Projects/PocketLotus/analysis/POCKETLOTUS_FEASIBILITY.md) for hardware dependencies and acceptance gates.
