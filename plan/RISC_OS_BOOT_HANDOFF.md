# RISC OS boot continuation handoff

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

Prepared 8 October 2026. This handoff captures the completed standalone diagnostic integration and defines the next software gate. This turn changes documentation only; it does not start RISC OS implementation or claim guest boot.

## Objective and boundary

Continue in `C:\Projects\PocketLotus` toward a genuine standalone Analogue Pocket RISC OS boot using the existing Archie chipset/APF integration. Target a suitably provisioned RISC OS 3.11 image and 4 MiB guest RAM as the initial compatibility candidate; verify the actual ROM identity, size, layout and behavior before treating it as suitable. Retain ARM26 PC/status semantics, MEMC, VIDC and IOC. Do not replace the guest with a native engine or switch to the separate openfpgaOS runtime.

The software gate is repeatable guest boot and usable guest interaction, with real keyboard protocol, IOC timers/interrupts, CMOS/RTC initialization and persistence, and an explicit storage strategy. Establish the minimum services required by the actual ROM first. A ROM initialization screen alone is partial progress. A storage adapter, ADFFS or IDE-ROM is not automatically required for a first ROM-only desktop boot; determine each dependency from the chosen route and record it separately.

Physical external APF/PSRAM timing, measured geometry/frame rate and stereo fidelity remain open qualification work. Continue independent guest implementation without falsely declaring those items closed. Protected JFD loading and Lotus gameplay/audio/video acceptance are later gates.

## Required starting reads

Read applicable live `AGENTS.md` files, including ancestors and any directories to be edited. None was found at `C:\`, `C:\Projects` or this project root during this handoff; recheck live state.

Read in full:

1. `plan/RISC_OS_BOOT_HANDOFF.md`, `plan/IMPLEMENTATION_STATUS.md`, `plan/implementation-results.json`, `plan/hardware-evidence.json` and `plan/SETUP_FAILURE.md`.
2. `docs/ARCHITECTURE.md`, `docs/BUILD.md`, `source-manifest.json` and `module-manifest.json`.
3. `plan/IMPLEMENTATION_HANDOFF.md` and the feasibility, ZIP, media and pinned reference manifests it references. This original handoff predates implementation: its statements about no root Git/source or missing build tools are historical. Current status and live checks supersede them.
4. Relevant actual RTL/build/package tools before editing. Trace the production loading, ROM overlay, memory, keyboard and CMOS paths in the pinned Archie source and their current Pocket replacements.

Use completed analysis as the starting point. Revisit it when a concrete implementation discrepancy warrants it. Do not spend the task repeating broad feasibility surveys.

## Accepted starting point

Version `0.1.5-diagnostic` is built and installed on the user's Pocket, firmware 2.7. It executes an original 688-byte ARM diagnostic through real external PSRAM, retained ARM26/MEMC/VIDC/IOC, APF loading/reset, VIDC video/sound and Pocket input.

Fourteen simulation/elaboration checks passed. Generic Yosys synthesis retained the chipset and reported zero final check problems. Actual Quartus synthesis, fitting, assembly, TimeQuest and timing audit passed for `5CEBA4F23C8`: 6,398/18,480 ALMs, 7,936 registers, 13 M10Ks and two PLLs. Reported internal setup/hold/recovery/removal/pulse-width and Gray skew checks passed in four timing models. Active external APF paths remain unconstrained; PSRAM delays are engineering budgets, not measured board closure.

Pocket evidence is positive but scoped:

- Display run: 39 complete eight-word log snapshots, all CPU/video/sound/peripheral counters advancing, independent system/pixel clocks live. User reports startup white bar, then persistent coloured bars and continuous tone.
- A input run: 25 progressing snapshots, three `600d0000`, fifteen `600d0010` while A held, seven `600d0000` after release. This verifies physical A through APF PAD, key mailbox and ARM heartbeat. It does not prove Archimedes keyboard protocol or other buttons.
- Earlier 0.1.4 froze. A directed real-MEMC/arbiter/PSRAM regression reproduced flyback DMA data entering a CPU cache fill; the generated MEMC fix drains accepted video/cursor bursts before pointer reset/new CPU fill. Sixteen boundary cases pass and the legacy path intentionally fails. Physical progress no longer freezes, but the faulty physical data return was not directly captured.

Preserve the passing flyback regression, original diagnostic mode, APF boot/reload protocol and independent instrumentation. Preserve prior results as versioned evidence before new builds overwrite working outputs. Do not rerun unchanged physical acceptance merely to rediscover established results; run new checks when changes warrant them.

Known diagnostic hashes:

- ARM binary: `4aeefc75ebc25f583fbd6ff0aedeb4ac7e65fd0f255a8698c1bf5aab73c8d8f7`.
- Raw RBF: `16f154a112b06d4ca4edd4d36da7c2f30dfc11716b11c3160b75f3f57fdda7b8`.
- Bit-reversed packaged RBF: `3c4051531b36d47c17430b22755b8e719792f73b45c37df2952d52c5a650f4de`.
- Diagnostic ZIP: `29003c92faec7c05d2a28fbf554db2b8637b6bb3532b74f7834ea7b1275c08e6`.

## Pinned sources, tools and implementation entry points

- Archie_MiSTer baseline: `references/Archimedes_MiSTer`, commit `7edeed510dbb80f505c1126b3a19b9416783989a`.
- PocketRiscV interface reference: `references/PocketRiscV`, commit `88430e4d049e112413221433af12f3c0604f5470`.
- PocketDoom interface reference: `references/PocketDoom`, commit `11cfcf96813603244ad6394f9ddc7eee36e5d9cc`.
- Quartus Prime Lite 25.1 with Cyclone V support: `C:\altera_lite\25.1std\quartus\bin64`; verified `25.1std.0 Build 1129 10/21/2025 SC Lite Edition`.
- Icarus/Yosys isolated under ignored `build/deps/oss-cad-suite`. Python and Git are available. Verify live tool availability; do not modify global PATH.

Important source paths: `rtl/core_top.v`, `rtl/pocket_chipset.v`, `rtl/pocket_host.v`, `rtl/pocket_reset.v`, `rtl/memory_arbiter.v`, `rtl/psram_word.v`, `rtl/pocket_video.v`, `rtl/pocket_audio.v`, `rtl/pocket_debug.v`, `rtl/pocket_probe.v` and `tools/prepare_chipset.py`.

Imported files under `rtl/vendor` retain pinned byte hashes. Make chipset changes through documented license-preserving generated derivatives or clearly manifested adapters; leave originals and reference checkouts untouched. Update source/module/license manifests for newly selected keyboard/CMOS/storage modules and identify embedded binary dependencies before import. Existing per-file LGPL/BSD/GPL/APF notices remain applicable; a README is not a blanket license. Two Amber SRAM wrappers lack individual headers and remain a distribution-review issue.

## Current service contracts and gaps

Physical CRAM0 capacity is 16 MiB; APF currently exposes the low 8 MiB. Guest RAM is 4 MiB and the diagnostic ROM window is backed at physical byte offset `00400000`. Trace MEMC's overlay and ROM decode rather than assuming APF file offsets equal guest CPU addresses. Check actual ROM byte order, interleaving and address mirroring.

Slot 0 currently loads the diagnostic through host command 0082. Loading/drain, 008F and target 0140 Ready to Run precede guest reset release. Unsupported IDs are rejected. Build a deterministic multi-asset boot contract if more assets are required: defined slot IDs, length/identity validation, all-required-assets-loaded fence, memory drain, reload/reset behavior and useful errors. Do not release the CPU on a partial ROM or stale readiness from a prior load. Preserve correct metadata author/shortname/directory identity and About version.

Guest reads are four physical words, wrapped within the cache line, then four contiguous MEMC ACKs. Writes ACK after physical commit with independent byte masks. Live host reads have no backpressure and are not qualified at maximum APF rate while guest DMA runs. Live host writes do not invalidate MEMC/Amber caches. Storage transfers therefore need a designed buffer/ownership/cache-coherency contract; reusing the diagnostic loader for arbitrary running-guest memory access is insufficient.

IOC timers/interrupts/control and keyboard ports exist. Archimedes keyboard inputs are currently inactive and the CMOS line is pulled high. FDC/IDE reads are unimplemented; no working disk service exists. Implement real service protocols required by the ROM, with supported behavior and explicit absence for deferred devices. Trace pinned wrapper behavior and port-level handshakes before designing replacements. Pocket gamepad input is currently raw diagnostic/joystick input, not a guest keyboard.

Provide practical Pocket guest navigation and menu/function-key access through a documented mapping. Support keyboard reset/identification/acknowledgement, make/break and interrupt behavior as required by the chosen ROM; test the actual protocol rather than only raw PAD bits. Decide how mouse interaction is supplied if the booted environment requires it. CMOS defaults must describe the implemented machine, not copied private data. Define RTC initialization/time progression and persistence location, protect existing user data and test reset/reload/save behavior. Explain any deliberate deterministic test clock separately from real hardware time.

VIDC guest programming may select modes beyond the original diagnostic's fixed timing. Trace the ROM's required clocks/modes and implement supported output behavior rather than assuming the fixed diagnostic clock proves guest display support. Preserve Lotus MODE 9's 320x256 active display and nominal 50 Hz guest timing for later gates, including palette writes during scanlines. Do not crop to 240 lines or substitute 60 Hz. Diagnostic success does not establish all guest modes, stereo fidelity or game audio.

## Dependencies and storage decision

No suitable RISC OS ROM or complete ADFFS package was provisioned in the completed analysis. Recheck private local assets without exposing or copying unrelated user data. Record actual file size/SHA-256, provenance and format for any supplied dependency. If the ROM is missing, identify the exact needed image and request that dependency while continuing independent RTL, packaging and synthetic protocol simulation. Never replace the ROM with the original diagnostic and claim RISC OS boot. Do not obtain proprietary content from unofficial mirrors or embed it in public source.

Identify independently:

1. RISC OS ROM: required for actual guest boot; verify compatibility with retained ARM26 and hardware model.
2. ADFFS runtime: later protected-JFD candidate, with its actual guest OS/RAM/storage requirements. It is not part of the ROM or necessarily needed for initial boot.
3. IDE podule ROM: required only if the chosen storage implementation uses that podule. The pinned source references a 16 KiB RiscDev IDE ROM; its bytes and redistribution terms were deliberately not imported. Audit separately from RISC OS.

Select a storage route from source evidence and the guest/ADFFS requirements. Implement required services or clearly defer them for a demonstrable ROM-only boot; do not let unexplained stubs masquerade as working hardware. If private HDF/boot files are used, keep them ignored and record their hashes and exact layout. No protected-media/game launch is part of this gate.

## Implementation and validation expectations

Make concrete source changes and continue autonomously through available work. Add focused meaningful simulations for new contracts: ROM mapping/order/reset overlay and load fencing, partial/wrong/reload assets, real keyboard transactions/IRQs, CMOS/RTC serial access/defaults/persistence, and storage transaction/coherency behavior if selected. Retain diagnostic/APF/MEMC tests affected by changes. Use an original synthetic ARM probe for independent hardware/service work when the real ROM is absent; label it as synthetic.

When a suitable ROM is available, capture guest-specific progress: ROM identity, reset and memory setup, initialized peripherals, boot stage/failure address or exception, guest-generated display, sustained CPU/DMA and responsive input. Define meaningful boot acceptance from the actual OS (for example, repeatable desktop or command environment with guest interaction), not a pattern matching the diagnostic. Bound slow full-ROM simulation explicitly and report limitations; passing synthetic tests are not OS boot evidence.

Run actual Quartus synthesis/fit/assembly/timing after HDL changes, inspect retained chipset resources and all relevant CDC/external-memory constraints, and package only the resulting successful build. Do not hide new failures with broad false paths. Record stage commands/exit codes, reports, source digest, utilization, achieved clock ratios, timing slack, warnings, unconstrained paths and package hashes. Preserve failed attempts and keep internal timing distinct from full board qualification.

Existing command entry points (inspect options before adapting to boot mode):

```powershell
Set-Location C:\Projects\PocketLotus
python tools/verify_analysis.py
python tools/module_manifest.py
python tools/simulate.py --test apf_elaborate
python tools/simulate.py --test memc_flyback
python tools/simulate.py --test memc_flyback --legacy-memc-flyback
python tools/simulate.py --test apf_boot
python tools/simulate.py --test apf_run
python tools/simulate.py --test diagnostic
python tools/synthesize.py
python tools/build_quartus.py --bin C:\altera_lite\25.1std\quartus\bin64
python tools/package_diagnostic.py --rbf build/quartus/output_files/pocketlotus.rbf
python tools/verify_package.py
python tools/record_results.py
```

Those commands build/package the existing diagnostic, not a RISC OS target by themselves. Extend or add reproducible boot-specific entry points, validators and private asset provisioning instructions. Keep the original diagnostic available as a regression/recovery target. `record_results.py` currently summarizes diagnostic results; extend evidence handling without replacing prior diagnostic claims with unrelated boot outputs.

The user authorized direct actions without SD backup for this project's core. The last mounted Pocket SD was `F:\`; check it is still the expected device and available before use. Use an explicit own-core file allowlist and readback hashes; preserve other cores, settings, saves and user assets. Do not format the SD or treat the whole drive as a build directory. A newly installed boot candidate must have a distinguishable version/About identity. Hardware tests requiring a power-cycle, controller action or observation require the user's participation; provide a concise concrete test after the build is ready and inspect actual `System/Logs` afterward. Debug Logging must be enabled after power-on. Installation/readback alone is not guest execution evidence.

Save boot implementation status, dependency inventory, exact commands/results, logs/hashes, observed failures and next unfinished gate in `plan`/`docs`, with generated/private artifacts ignored. Keep source, simulation, generic synthesis, actual fit/timing, hardware OS boot and gameplay evidence separate. If a tool/dependency blocks a specific check, state the precise limitation and finish independent work; do not mark the blocked gate passed.

## Preservation and later gates

Preserve the supplied JFD/ZIP hashes, all reference checkouts, imported source notices and user data. Run `tools/verify_analysis.py` at start and after relevant work. The current root Git working tree has the implementation folders untracked; preserve that state and do not publish or broadly stage private material.

Keep originals in `Lotus`, extracted media under `analysis/media`, ROMs, ADFFS/IDE binaries, private HDF/CMOS data, references and generated outputs excluded from publication. Review exclusion paths for any new asset directory. No public push, release or upload is requested.

The 0-3 ZIP remains the ADFFS runtime candidate; retain 0-2 for loader decryption/patch evidence. These contain compiled ARM/RISC OS programs and assets, not rebuildable Lotus engine source. Disk 1 has a protected bad-CRC sector at cylinder 79/head 1/sector 0; plain ADF conversion loses that behavior. Do not flatten or silently patch protection to advance a boot claim. After OS boot, prove the chosen protected JFD path before Lotus title/demo/race, controls, audio/video and disk transitions on real Pocket hardware.
