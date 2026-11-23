# First implementation milestone status — 8 October 2026

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

The standalone Pocket diagnostic integration is implemented, simulated, built
for **5CEBA4F23C8** and packaged with its genuine Quartus bitstream. The pinned
ARM26, MEMC, VIDC and IOC execute the original ARM diagnostic through physical
PSRAM arbitration and drive APF video/audio/status. This is an original
688-byte diagnostic, not a playable Lotus core. Pocket logs verify sustained
CPU/DMA execution and A press/release; the user reports persistent coloured bars
and continuous tone. **Full board timing, measured geometry/frame rate and
stereo fidelity remain unqualified.** No RISC OS boot or game result is claimed.

The user-reported first hardware launch on OS 2.7 failed with “Load error in
'core' / General error / Error in core setup” immediately after Run, before
asset selection. Version **0.1.1-diagnostic** fixes a reproduced 0082 host-write
rejection and two oversized metadata labels. The corrected documented boot
and second-load simulation pass.
Read [setup failure and regression evidence](SETUP_FAILURE.md) and
[separate hardware evidence](hardware-evidence.json).
Installed 0.1.1 hashes were verified on the SD. The device's boot trace then
confirmed a metadata/directory lookup mismatch before any FPGA execution.
Version **0.1.2-diagnostic** fixes that identity and adds About info.txt, with
the identical rebuilt 0.1.1 bitstream. The user then loaded the diagnostic and
observed a white bar at the bottom and a tone. Setup and asset selection work
by user report; the expected stripe display was not observed, and internal
diagnostic status, stereo fidelity and input remain unmeasured.
Version **0.1.3-diagnostic** adds a VIDC-to-APF video adapter correcting
single-cycle sync events, VS-to-HS spacing and zero RGB during blanking.
Directed receiver and complete chipset simulations pass; replacement hardware
acceptance is a separate gate.
The new 0.1.3 bitstream, core metadata and About information were installed
directly on `F:\`; all twelve diagnostic file hashes match the verified local
package. No SD backup was made. Other cores and user assets/settings/saves
were not changed. The user retry still showed a white bar and tone, followed
by brief thin coloured stripes that disappeared. The new device trace confirms
bitstream loading, the 688-byte transfer, Ready to Run and Reset Exit completed.
Internal chipset status was not recorded in that build. Version
**0.1.4-diagnostic** adds periodic coherent CPU/DMA snapshots through APF Debug
Event Log; it is an instrumentation build for this unfinished hardware gate.
The 0.1.4 build completed all five Quartus stages at exit 0 with nonnegative
reported timing/skew slack in all four models. It was installed directly on
`F:\`, changing only the bitstream, core.json and info.txt; all twelve installed
hashes match the verified package. The physical trace now contains 33 identical
CPU/DMA snapshots over 16 seconds: ARM result `600d0000`, CPU 138,300, video
143,760, sound 2,176, peripheral 10,398 and last acknowledged CPU address
`03800188`. Initial setup reached success, but progress is frozen in exported
status. The APF logger stayed responsive. Stopped clocks, stalled execution
and stale mailbox status remain distinct possibilities. Version 0.1.5 adds
independent clock/ACK and memory-state probes and fixes a reproduced DMA boundary defect.
The final 0.1.5 build passed all five Quartus stages and reported timing/skew
checks in four models. Fourteen simulation/elaboration checks pass, plus the
expected legacy flyback failure. Direct installation changed three files and
all twelve installed hashes match. The Pocket retry now reports a white bar
at startup, a continuous tone and coloured striped bars remaining on screen.
The new physical trace contains 39 complete eight-word snapshots; all 39
have ARM result `600d0000` and strictly increasing CPU, video, sound and
peripheral acknowledgements, with independent system/pixel clock probes live.
CPU acknowledgements increase from 227,273 to 8,550,237; video from 247,532 to
10,194,688; sound from 3,780 to 155,060; peripheral from 18,135 to 741,871.
The earlier freeze did not recur. This is sustained diagnostic hardware
execution plus visible/audible output, not measured geometry/frame rate or
stereo/sample fidelity. A separate physical input trace now verifies press,
hold and release: three snapshots `600d0000`, fifteen `600d0010` (A bit 4),
then seven `600d0000`. All 25 snapshots continue CPU/video/sound/peripheral
progress. Physical A input through APF PAD, the key mailbox and ARM heartbeat
is verified; other keys and the later Archimedes keyboard protocol are untested.

The flyback regression returned framebuffer data `76543210` for a CPU read
whose RAM contained `cafe0000`. The corrected generated MEMC derivative drains
accepted video/cursor DMA before resetting pointers and starting a CPU cache
fill. Sixteen boundary phases pass. This is a proven source/simulation defect;
the corrected physical run no longer freezes. The faulty physical DMA return
was not directly captured, so the mechanism remains separately demonstrated
by the directed regression.

Read [build commands](../docs/BUILD.md), [architecture](../docs/ARCHITECTURE.md),
[module/license manifest](../module-manifest.json), [preserved source hashes](../source-manifest.json)
and [actual machine-readable results](implementation-results.json).

| Evidence layer | Actual result |
| --- | --- |
| Preservation | Original JFDs and three ZIP hashes unchanged; all materialized reference checkouts clean; 11 references verified; all 43 imported files retain their pinned byte hashes |
| Source | Real APF top, 43 selected Verilog files, 46 modules, 589 unchanged Pocket pin/I/O assignments; ARM26/MEMC/VIDC/IOC connected and observable; original restricted ARMv2 assembler |
| APF elaboration | Icarus exit 0; real bridge/controller/command/scaler modules; functional vendor simulation models |
| Host/reset simulation | Exit 0; 129 writes drain before CPU release, 128 ordered reads at 88 bridge clocks, coherent status, reset and sticky overflow |
| APF command/boot simulation | Exit 0; actual BRIDGE Setup/Idle responses; unsupported 0082 write ID rejected; slot 0 loads 688 bytes through 0082; 008F/drain/0140 Ready to Run handshake; ARM word/byte checks, reset-enter and second 0082 reload/re-execution; old RTL failed this documented-sequence test |
| I2S simulation | Exit 0; 48 kHz requested framing, one-bit delay, MSB order, stereo, padding, coherent changed samples and reset |
| APF video simulation | Exit 0; three 320x256 frames, 511x313 ideal timing, single-cycle HS/VS, VS/HS/DE gaps, zero blanking RGB and unchanged active pixels; former direct output fails the blanking assertion |
| Intel-model DDR simulation | Exit 0; actual pinned DDR wrappers and installed Intel model; three decoded 320x256 frames, RGB/control half alignment, blanking, sync gaps and 19.992875ms cadence; not electrical/scaler qualification |
| APF debug simulation | Exit 0; actual target FSM, Ready-to-Run priority, 32 ordered marker/data events, delayed host acknowledgements, coherent snapshots, pending-event cancellation and fresh Ready to Run after reset/reload |
| Sustained APF core simulation | Exit 0; actual core_top load/reload and ARM/DMA execution, 112 acknowledged coherent-status/independent-probe debug events, three qualified frame boundaries decoded through APF DDR wrappers, 320x256/gap/blanking/19.992875ms checks; interval accelerated only for reporting |
| VIDC pixel FIFO simulation | Exit 0; 128 words/512 bytes, word-to-byte order, wrap/full, overflow rejection, underflow silence, CE stalls and reset |
| VIDC register-write simulation | Exit 0; 49 ordered words, held-request deduplication, full backpressure, retained pending MEMC ACK, wrap and drain; directed boundary probe, separate from ARM execution |
| Independent probe simulation | Exit 0; live clocks/ACKs, stopped ACKs with clocks live, stopped generated clocks with bridge flags updating, reset while stopped |
| MEMC flyback boundary simulation | Exit 0; sixteen video/cursor read and ACK boundary phases; four DMA beats drain before CPU cache miss/hit data; legacy path reproduces DMA-to-CPU cache corruption with expected exit 1 |
| Physical PSRAM simulation | Exit 0; both dies and boundary, no alias, latched commands, independent byte enables, zero-mask preservation, 70 ns read delay and commit/recovery |
| Complete chipset diagnostic | Exit 0; word/STRB/two-byte halfword tests, STMIA framebuffer, IOC timers/control, three qualified 320x256 frames, 19.992875 ms ideal frame period, zero qualified pixel FIFO underflows, contended host access, CPU/video/sound activity, nonzero stereo and input observation |
| Generic Yosys synthesis | Exit 0; retained ARM26/MEMC/VIDC/IOC hierarchy; final check zero problems; 48,831 generic cells including print cells and vendor black boxes; not Cyclone V utilization |
| Quartus Analysis & Synthesis | Exit 0; actual vendor RAM/DDR/PLL elaboration; 672 warnings, including inactive pins/unused legacy paths and primitive width adaptations |
| Quartus fitting | Exit 0; 6,398/18,480 ALMs (35%), 7,936 registers, 33,056 memory bits, 13/308 M10Ks, 2/4 PLLs, 0 DSPs; 7 warnings |
| Quartus assembly | Exit 0; genuine 1,041,148-byte 0.1.5 RBF produced |
| TimeQuest and audit | Both exit 0; reported setup/hold/recovery/removal/pulse-width and Gray skew checks pass across slow/fast 1100 mV models at 0°C and 85°C; active external APF I/O remains unconstrained |
| APF packaging | Complete local diagnostic ZIP with bit-reversed RBF, original ARM binary, metadata, manifests and source notices; documented metadata profile, hashes and ZIP CRCs checked |
| SD installation | 0.1.5-diagnostic; three changed files; all twelve allowlisted installed hashes match; file readback only |
| Pocket hardware | 0.1.5: 39 advancing CPU/video/sound/peripheral snapshots and live independent clocks; user reports persistent coloured bars and continuous tone after startup white bar. Separate 25-burst trace verifies A press/hold/release with CPU/DMA progress. Physical geometry/frame rate, stereo fidelity and external timing unqualified |
| RISC OS / protected JFD / Lotus | Not tested |

The final diagnostic reports `cpu=44876`, `peripheral=2274`, `video=30844`,
`sound=472`, `host=304`, `colored=211200`, `timers=2597`, `audio=0040/0040`,
`underflows=0`, result `600d0010`, at simulated 76.72453446 ms. Counters represent
transactions/observations, not guest instruction counts or game fidelity.
The binary SHA-256 remains
`4aeefc75ebc25f583fbd6ff0aedeb4ac7e65fd0f255a8698c1bf5aab73c8d8f7`.

| Timing model | Worst setup ns | Worst hold ns | Worst recovery ns | Worst removal ns | Gray skew slack ns |
| --- | ---: | ---: | ---: | ---: | ---: |
| Slow 85°C | 0.765 | 0.388 | 11.447 | 0.823 | 8.287 |
| Slow 0°C | 0.867 | 0.377 | 11.562 | 0.770 | 8.210 |
| Fast 85°C | 3.346 | 0.169 | 12.634 | 0.302 | 10.546 |
| Fast 0°C | 3.598 | 0.098 | 12.716 | 0.273 | 10.635 |

The audit matches 60 Gray source registers including duplicates and all 56
first-capture bits, plus nonempty status/controller/audio payload and PSRAM
capture collections. All 22 independent probe first captures and all 22 second
captures match; later stages remain timed. There are zero missing/illegal clocks, loops, latches,
PLL cross-check issues or incomplete multicycles. **Four active input ports
and 25 active output ports remain unconstrained** (29 input and 43 output
paths for setup and hold). These cover APF SPI/controller, scaler/video/audio
and diagnostic GPIO. The larger raw missing-output-delay count includes
inactive constants. No broad asynchronous clock groups hide those paths.
PSRAM input/output delays remain engineering budgets rather than measured
board specifications. Internal reported timing success is not full board closure.

Quartus implements nominal CPU **42.001281738 MHz**, pixel **8.000244141 MHz**
and audio MCLK **12.291145169 MHz** from a nominal 74.25 MHz board reference.
The pixel companion is derived at 90°. Those PLL ratios imply approximately
50.01934 Hz diagnostic video and 48.012286 kHz I2S; oscillator tolerance,
jitter and board skew are unmeasured. TimeQuest's three-decimal period output
is rounded; ratios, not reciprocals of rounded periods, give these nominal
rates. Functional simulation uses the ideal requested clocks. Preserve MODE 9
320x256 and nominal 50 Hz through later platform/game gates.

Simulation and real timing analysis led to concrete integration fixes:
contiguous four-beat MEMC read acknowledgements; accepted DMA drain at flyback; correct sound DMA stall/SFR
startup; a 32-word pixel FIFO covering PSRAM latency; correct MEMC DMA pointers
and enable ordering; APF ID acknowledgement and deterministic FSM startup;
latched load/drain release; correct I2S bit delay; preserved Gray MSBs so all
bits remain constrained; stable FIFO/mailbox timing bounds; pin-specific reset
synchronizer exceptions; pixel-domain queued VIDC palette/timing/audio writes
with CPU backpressure; synchronized flyback/hsync; and a physical PLL startup
reset pulse. Originals and source notices are preserved in every derivative.

The first fitting attempt failed on unsupported TimeQuest syntax. The first
successful fit produced setup/recovery violations; the next fit resolved CDC
paths but missed Amber setup by 0.557 ns. Standard Fit/aggressive performance
from the pinned Archie project resolved the remaining path with seed 1.
An instrumentation-only 0.1.5 fitter attempt crashed with an access violation
(exit 2); assembly/timing were not run. An unchanged mapped-design retry passed.
That bitstream was not installed, and the final DMA fix was rebuilt from synthesis.
Automatic register retiming/asynchronous pipelining stay disabled. Earlier
attempts are retained under ignored `build/quartus/attempts`.

Quartus is installed at `C:\altera_lite\25.1std`, version
`25.1std.0 Build 1129 10/21/2025 SC Lite Edition`. Its earlier absence and
failed installer-download discovery are historical, not current blockers.
Icarus is `14.0 (devel), s20260301-538-gf45ffabed-dirty`; Yosys is
`0.69+260, dcd59343b`, isolated under ignored `build/deps/oss-cad-suite`.
No system PATH or reference checkout was modified. The TimeQuest warning
about long fractional clock relationships is retained; MTBF is not calculated
because the tool's specified-synchronizer/toggle-rate metadata is absent.
LogicLock subscription, PLL compensation and inherited SPI clock routing/I/O
assignment warnings remain recorded; no successful exit erases them.

The local package is `build/package/PocketLotus.Diagnostic.zip`. Read its
`INSTALL.txt` and checksum manifest before a hardware run. The ZIP is complete
as a diagnostic build package; it does not establish Pocket acceptance or
source-publication readiness. No source publication, upload or release occurred.
Game/ROM content, private data, reference checkouts and generated outputs stay
ignored. The two pinned Amber SRAM wrappers lack individual license headers;
review their provenance before distribution. No game/ROM dependency is bundled.

**Next unfinished gate:** physical external timing, geometry/frame rate and
stereo qualification remain open. A press/hold/release is verified, and the
earlier execution/display freeze no longer reproduces in 0.1.5.
Establish and constrain the external APF
SPI/controller/scaler/audio board timing requirements and measure the remaining
320x256 nominal 50 Hz video and stereo properties. APF loading/reset, sustained
CPU/DMA and physical A press/release have runtime evidence. No physical
pin/clock measurement is available in this session; SD logs establish runtime
progress and the display/tone observations are user reports. Directed
functional tests are not a formal proof of every CDC/arbitration sequence.

After diagnostic hardware acceptance, implement RISC OS boot with real
keyboard/CMOS/RTC and chosen storage services. Identify RISC OS ROM, ADFFS and
IDE-ROM dependencies separately; FDC/IDE services are currently omitted.
Then verify protected JFD loading before Lotus gameplay/audio/video acceptance.
Retain 0-3 as the ADFFS runtime candidate and 0-2 as loader decryption/patch
evidence. Plain ADF conversion loses disk 1 protection. The ZIPs are compiled
ARM/RISC OS programs/assets, not rebuildable engine source; preserve all
original hashes and the game's artwork/audio.
