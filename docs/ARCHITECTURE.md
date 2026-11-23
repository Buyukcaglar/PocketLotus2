# Pocket diagnostic integration

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

The source target is `apf_top` on Cyclone V `5CEBA4F23C8`. It uses the real
Pocket APF bridge, controller and scaler interfaces. `core_top` connects the
pinned Archie ARM26, MEMC, VIDC, IOC and latch modules to new Pocket services.
The original chipset is executing code and producing DMA, RGB and stereo
samples; there is no independent test-pattern generator.

| Service | Implementation and contract |
| --- | --- |
| CPU and address translation | Amber ARM26 and MEMC at requested 42 MHz; preserve 26-bit PC/status semantics and reset ROM overlay |
| External memory | CRAM0 asynchronous multiplexed address/data bus, both chip selects, two physical 16-bit cycles per 32-bit word; four independent byte enables |
| Arbitration | Alternating eligible host/guest ownership at transaction boundaries; guest read is four physical words, wrapped within its 16-byte line, then four **contiguous** MEMC acknowledgements; writes acknowledge after physical commit |
| APF loading | Host 0082 writes slot 0 at physical byte offset `00400000`; asynchronous request/response FIFOs; minimum qualified interval 88 bridge clocks; overrun sticky and prevents guest release; 008F/drain followed by target 0140 Ready to Run before host reset-exit |
| Reset | PLL lock, successful loading completion, queued-write drain and settling precede release; release synchronized separately into CPU/pixel domains; loading fence remains latched during CPU/DMA activity |
| Observation | Coherent six-word status snapshot at `F0000000..F0000014`: diagnostic result, CPU acknowledgements, video acknowledgements, sound acknowledgements, peripheral acknowledgements, last CPU address |
| Runtime evidence | Half-second APF 0152 event producer uses the same coherent bridge snapshot; six marker/data pairs; host acknowledgement fences parameters, Ready to Run has priority and guest reset cancels pending logging |
| Input | Coherent controller mailbox into CPU domain; raw input bits visible at diagnostic IOC bank 6 and active-low joystick latches |
| Video | Retained VIDC palette/DMA/timing RGB, expanded 4 bits to 8 bits per channel; registered APF adapter emits single-cycle HS/VS, delays a coincident first HS four cycles after VS and zeros RGB while DE is low; requested 8 MHz and 90-degree companion clock |
| VIDC register writes | CPU/MEMC events queue into the pixel domain; a full queue holds CPU ACK and retains a pending MEMC ACK; palette, control, timing and sound configuration update in their consuming domain |
| Audio | Retained VIDC sound DMA and eight-channel mixer, coherent stereo mailbox, 12.288 MHz MCLK, 48 kHz 16-bit I2S with padding |

The physical memory address space is 16 MiB on CRAM0. APF currently exposes
only the low 8 MiB; MEMC's diagnostic guest uses 4 MiB RAM and its ROM window
backed at physical 4 MiB. CRAM1, SDRAM and SRAM are inactive. Async PSRAM mode
uses latched addresses, six access clocks and two recovery clocks; WAIT is
not used. The pin model checks byte masks, write/address timing and a 70 ns
read-access budget. This is functional/timing-budget simulation, not proof
of the actual fitted board bus or the exact PSRAM operating-mode assumptions.

Fabric, FIFO and audio reset release use two local clock edges in each domain.
CPU and VIDC receive their respective guest reset releases rather than ORing
two independently released resets onto both domains.
Both physical PLLs receive a sixteen-reference-clock startup reset. Flyback
and hsync are sampled through two stages before MEMC/IOC/DMA CPU-domain use.

APF RAM load/readback is qualified with the guest reset. Concurrent directed
host/CPU/video/sound arbitration is checked separately. The maximum-rate APF
read protocol is **not** qualified while the guest is running: it has no
backpressure and a guest four-word transfer can exceed that response interval.
Use coherent status reads while running. Live host writes also do not
invalidate MEMC/Amber caches; later storage services need their own contract.

Two independent PLLs request machine/pixel and audio clocks. Combining 42,
8 and 12.288 MHz in one VCO/divisor family is inappropriate. Requested
frequencies and phases are requests; the final implemented ratios at nominal
74.25 MHz give CPU 42.001281738 MHz, pixel 8.000244141 MHz and audio MCLK
12.291145169 MHz, with a 90-degree companion. The SDC bounds
Gray-pointer and mailbox payload paths without false-pathing those same
paths. Gray registers retain separate MSBs so all 56 capture bits stay in the
bounded collection. Quartus Lite's clock-relative maximum delays are paired
with loose cross-domain minimum delays for stable FIFO/mailbox data. Only
identified single-bit first captures and asynchronous reset-chain clear pins
are false-pathed; subsequent stages and downstream reset sinks remain timed.
PSRAM multicycle constraints describe the controller's access budget.
The actual four-model audit passes reported setup/hold/recovery/removal and
Gray skew checks. Active external APF SPI/controller, scaler/audio and GPIO
paths remain unconstrained; their board requirements and PSRAM budgets need
physical qualification. See the separate evidence in implementation status.

`source-manifest.json` locks every imported byte and notice to a source commit.
`module-manifest.json` records the selected modules and dependencies. References
remain unchanged. Eight generated derivatives preserve source headers:

1. MEMC declaration ordering, with continuous equations unchanged; preserve
   accepted video/cursor DMA ownership across flyback until all four ACKs
   complete, then reset the pointers and allow a new CPU cache fill. Block new
   video/cursor grants during flyback. A simulation-only legacy switch retains
   the original cancellation logic for the failing boundary regression.
2. VIDC FIFO: replace unsafe binary-pointer crossing with Gray pointers,
   explicit wrap/full accounting, and reset release independent of read enable.
3. VIDC: explicitly tie the previously omitted sound DMA stall input low and
   enlarge video DMA FIFO from 8 to 32 words to cover Pocket PSRAM/CPU burst latency;
   apply queued palette/control/timing/audio writes on clkpix while retaining
   CPU-clock DMA and using synchronized hsync for its stall conditions.
4. VIDC audio: explicitly initialize SFR disabled so its divider cannot be
   poisoned by an unknown value before the ARM program enables sound.
5. APF top: declaration ordering.
6. APF controller: prior declarations and separate procedural tri-state drivers.
7. APF bridge peripheral: prior declarations and separate tri-state drivers.
8. APF command handler: declaration ordering, explicit FSM/command startup,
   deterministic unused fourth response word and a bounded 0152 debug event
   path. The integration acknowledges a data-slot request only after its new
   ID is visible. Events do not access guest memory or stall CPU/DMA.

The diagnostic assembly is original. The restricted ARMv2 assembler rejects
unsupported instructions and produces deterministic binary/hex/listing files.
It tests word and byte accesses (two byte stores represent an ARM2 halfword,
since ARM2 lacks native STRH/LDRH), IOC control and timer activity, fills a
40 KiB 320x256 framebuffer using STMIA, programs VIDC palette/timing, sets up
a synthetic signed sound buffer, and keeps checking RAM/input in a heartbeat.
No RISC OS, proprietary ROM or game content is required.

Independent 0.1.5 bridge-domain probes observe divided system/pixel clocks and
CPU/video/sound/peripheral acknowledgement-count bits through two capture
stages. Their edge observations and reset/MEMC/arbiter/PSRAM flags bypass the
status mailbox. The original six words remain coherent; the added flags are
individually synchronized and only interpreted as a state when stable. This
distinguishes a stale mailbox, stopped generated clocks and stalled transfers
without issuing guest RAM transactions or changing guest execution. Only the
first probe captures and raw-counter asynchronous-clear pins are false-pathed;
the second captures remain timed and are checked as nonempty audit collections.

The diagnostic uses 511 total pixels by 313 lines at 8 MHz: 19.992875 ms per
frame, approximately 50.0178 Hz. Active display remains 320x256. This qualifies
the diagnostic's timing in simulation; it is not a test of Lotus MODE 9 or
Pocket scaler acceptance. Guest nominal 50 Hz must remain through later gates.

FDC registers/media service, IDE podule and its ROM, CMOS/RTC, and Archimedes
keyboard protocol are deferred. FDC/IDE reads return unimplemented values;
there is no disk controller masquerading as a working service. IOC timers,
interrupt logic, control registers and keyboard ports are retained; keyboard
inputs are inactive and the CMOS line pulled high. The separate later
dependencies are a lawfully provisioned RISC OS ROM, the required ADFFS runtime,
and a separately identified IDE ROM if IDE is chosen. None is packaged here.

Version 0-3 ZIP remains the preferred ADFFS runtime candidate; retain 0-2 for
loader decryption/patch evidence. These ZIPs contain ARM/RISC OS programs and
assets, not rebuildable engine source. Protected disk 1 needs JFD/protection
semantics: plain ADF conversion loses them. Preserve original hashes and media
through the RISC OS boot, protected JFD, then Lotus hardware gameplay/audio/video
gates. Do not promote diagnostic results into those gates.
