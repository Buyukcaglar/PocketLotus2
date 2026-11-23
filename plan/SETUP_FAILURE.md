# Pocket setup rejection — 8 October 2026

> **Superseded on 22 November 2026.** This document belongs to the retired hardware chipset route. The project now recompiles the game for openfpgaOS; see the [roadmap](../plan/ROADMAP.md) and [port architecture](../docs/PORT_ARCHITECTURE.md).

The user installed the first diagnostic package on a Pocket with Analogue OS
2.7. Immediately after **Run**, before any file could be selected, it showed:

```
Load error in 'core'
General error
Error in core setup
```

This is a user-reported failed hardware launch. No ARM diagnostic execution,
video, audio, PSRAM or controller acceptance was observed. The attempted ZIP
SHA-256 is `40a21999cdd04d2ba9e1d009affdf8135dbeeb31f775cc943f18f88c143dd422`.
The original archive, manifests, previous implementation results and previous
APF boot test are preserved under ignored
`build/hardware-attempts/20261008-setup-error`.

Three concrete defects were found:

1. `core_top.v` rejected all host **0082 Data slot request write** operations.
   Pocket uses that command to load assets into core RAM. The reset/loading
   gate also watched 0080 (reads out of the core) instead of 0082. The previous
   test drove 0080 before writing memory, so its passing result did not qualify
   the actual host loading sequence.
2. The data-slot name was 23 characters; the documented maximum is 15.
3. The controller mapping name was 22 characters; the maximum is 19.

Sources: Analogue's [boot process](https://www.analogue.co/developer/docs/openfpga/core-boot-process),
[host commands](https://www.analogue.co/developer/docs/openfpga/host-target-commands),
[data definition](https://www.analogue.co/developer/docs/openfpga/core-definition-files/data-json)
and [input definition](https://www.analogue.co/developer/docs/openfpga/core-definition-files/input-json).
The core's `version_required: 2.2` and numeric `cartridge_adapter: 0` are
documented valid values; OS 2.7 meets that version requirement.

Version **0.1.1-diagnostic** accepts slot-0 host writes, watches that write
request for loading/reset, and shortens both labels. The ARM diagnostic and
pinned vendor imports retain their hashes. The revised APF test reads actual
BRIDGE responses, checks Setup before loading, rejects an unsupported write
ID, loads slot 0 through 0082, sends 008F and RTC notification, observes and
acknowledges target **0140 Ready to Run**, checks Idle and held CPU reset, then
releases reset and observes ARM word/byte checks before reset-enter.
It then reloads through a second 0082, checks that the previous ready latch is
revoked, waits for another drained Ready to Run handshake and re-executes ARM.

The revised test **failed against the previous RTL** with
`APF command 0082 returned 4f4b0002`, and **passed after the fix**. Both results
are retained; `documented-boot-regression.log` and its result JSON are in the
failed-attempt directory. The metadata validator also rejects both original
oversized labels and passes the corrected diagnostic profile. It checks the
profile's documented fields/types/lengths/counts, not Analogue OS's closed
parser implementation. Packaging and verification invoke it automatically.

Commands from `C:\Projects\PocketLotus`:

```powershell
python tools/validate_apf.py
python tools/simulate.py --test apf_boot
python tools/synthesize.py
python tools/build_quartus.py --bin C:\altera_lite\25.1std\quartus\bin64
python tools/verify_analysis.py
python tools/package_diagnostic.py --rbf build/quartus/output_files/pocketlotus.rbf
python tools/verify_package.py
python tools/record_results.py
```

Exact commands, exit codes, report hashes and replacement archive checksum are
recorded in `implementation-results.json`; the user report is separately saved
in `hardware-evidence.json`. No device trace establishes which defect produced
the reported early error. These fixes address demonstrated defects, while
acceptance of the replacement on the physical Pocket remains pending.

## Follow-up: 0.1.1 installed correctly, directory mismatch confirmed

The user reported the same early error after installing 0.1.1 and provided
USB SD access as `F:\`. All eleven installed APF/platform/asset files matched
the 0.1.1 package hashes exactly, including the genuine RBF_R. Device metadata
also confirmed firmware 2.7. About did nothing because no optional `info.txt`
had been packaged.

After the user enabled Debug Logging and retried, the complete 115-byte log
ended with:

```
APF Debug Log
Pocket OS version 2_7

Start
Load core normally
Opening /Cores/PocketLotus.PocketLotusDiag/core.json
```

That requested directory did not exist. The installed directory is
`/Cores/PocketLotus.Diagnostic`, but metadata declared author `PocketLotus`
and shortname `PocketLotusDiag`. Analogue's [packaging rules](https://www.analogue.co/developer/docs/openfpga/packaging-a-core)
require the folder to match `author.shortname`. This trace establishes an
actual filesystem lookup failure before bitstream/bridge/ARM execution; the
previous protocol and label fixes did not address it.

Version **0.1.2-diagnostic** changes the metadata shortname to `Diagnostic`
and adds About `info.txt` with the version. No RTL, ROM, firmware binary or
bitstream changes were made. The existing passing 0.1.1 synthesis/fit/timing
results apply to the identical bitstream. The validator now rejects mismatched
directory identities; packaging includes info.txt and verification checks its
version against metadata. Original imports/media remain unchanged.

The failed 0.1.1 package, installed core files, exact debug log and SD readback
hashes are preserved under ignored
`build/hardware-attempts/20261008-setup-error-0.1.1`. Only this core's changed
metadata and About file are installed on the user's SD; other cores and user
assets/settings/saves are preserved. SD readback hashes and device retry
results are recorded separately from local package/build evidence.

## Follow-up: core loaded, display contract violation found

After 0.1.2 was installed directly and read back on `F:\`, the user reported:
“core ran, I chose diagnostic then a white bar appeared on the bottom along
with heard a tone”. Setup/asset selection now work by user report. The
expected palette-stripe image was not observed. Tone alone does not qualify
stereo, sample fidelity or the diagnostic success register. No new boot log
was available after the power cycle; Analogue's developer logging option
resets on power-off.

Source inspection against Analogue's [VIDEO bus contract](https://www.analogue.co/developer/docs/openfpga/bus-communication)
found the previous direct assignments violated two requirements: VIDC's
width-programmed sync levels were sent instead of single-cycle APF events,
and nonzero RGB was sent while DE was low. APF interprets blanking RGB as
feature/end-of-line control data, including scaler-slot commands. VS/HS also
started together rather than respecting the required spacing. These are
demonstrated source/protocol defects; the exact contribution to the reported
white bar remains unmeasured.

Version 0.1.3-diagnostic adds `rtl/pocket_video.v`, preserving guest pixel and
frame timing while registering RGB/DE, emitting sync events, spacing the
first HS four cycles after VS and outputting zero RGB in blanking. The
directed receiver test checks three 320x256 frames, single-cycle events,
VS/HS/DE gaps, 511x313 timing and unchanged active pixels. Its legacy-output
regression fails on blank RGB `ffffff`. The complete ARM/chipset simulation
also checks exported APF geometry and protocol. New Quartus results and SD
installation hashes are recorded when the rebuild finishes; display hardware
acceptance remains a separate gate.

The 0.1.3 rebuild completed with all five Quartus stages at exit 0: 6,217 ALMs,
7,541 registers and a 1,030,084-byte genuine RBF. Reported timing and Gray skew
requirements pass across four models; external APF timing remains unqualified.
The complete chipset simulation also passed with `600d0010` and zero qualified
pixel FIFO underflows. Raw RBF SHA-256:
`890bfcea0d8337fe5cc56fc2d61b43d56ac95c7274109585ee7d2b16c5cf937c`.
The verified ZIP SHA-256:
`060b74df5aa04ca5da499ccf8fda5636d81083f1da2b41d9b5fc73b855fc9bb5`.
`python tools/install_diagnostic.py --root F:\` changed only core.json,
info.txt and bitstream.rbf_r, then verified all twelve installed hashes. No
SD backup was made. The user retry is pending; installation is not execution
evidence.

## Follow-up: 0.1.3 display still fails; runtime instrumentation

The user corrected the observed sequence: white bar and tone first, then
brief thin coloured stripes which disappear. A new 5,261-byte device trace
confirms the correct directory, successful bitstream load, full 688-byte asset
transfer, Ready to Run and Reset Exit. Its local copy/hash are recorded in
`hardware-evidence.json`. No trace in 0.1.3 reports internal CPU or video status,
so this is a display failure with successful setup, not diagnostic acceptance.
Only the core's own video persistence settings were inspected; no setting,
other core, save or user asset was changed.

Version 0.1.4 adds an original periodic APF 0152 event producer using the existing
coherent CPU-to-bridge mailbox. Every nominal half-second, marker/data pairs
report diagnostic result, CPU/video/sound/peripheral transaction counts and
last CPU address. The target FSM holds each parameter until host completion,
gives Ready to Run priority and cancels a pending log request on guest reset.
No guest RAM reads or execution stalls are introduced. This build gathers
evidence for the remaining fault; no display fix is claimed.

New directed tests verify 24 ordered events, coherent snapshots while live
status changes, delayed acknowledgements and reset/reload after an unacknowledged
event. Intel's installed DDR model passes three decoded frames through the
pinned APF wrappers. Our functional DDR model was corrected to capture both
halves at the rising edge. A sustained core_top test now follows actual APF
load/reload, services debug events while ARM/DMA run and decodes the serialized
video stream. Its reporting interval alone is accelerated to ten milliseconds;
guest clocks and 320x256/nominal 50 Hz timing are preserved.

An interim instrumentation fit and long simulation were intentionally stopped
after adding cancellation of pending logging on reset, then restarted from
the revised source. The interrupted Quartus stage returned 4294967295 and
dependent stages were not run; those build records remain in ignored attempts.
The actual final commands/results and later hardware retry remain separate.

The final 0.1.4 sustained APF run passed at simulated 76.907290096 ms, including
84 acknowledged log events and qualified serialized frames. Quartus completed
all five stages at exit 0: 6,356 ALMs, 7,733 registers and a 1,037,376-byte RBF.
Reported timing/skew requirements pass in four models; full external board
timing remains unqualified. Raw RBF SHA-256:
`c14e3f81ab65af11ba50c000e6cde321ba7d761c803e78f3ae55b5fae7ee54ad`.
Verified ZIP SHA-256:
`213f4994a543ce764479351c707690ac167dc23756e2138cc5a1229f14bee7dd`.
Direct installation changed three files and read back all twelve hashes.
The instrumented physical run completed; the display issue remains open.

## Follow-up: 0.1.4 exports frozen runtime status

The 36,941-byte trace `PocketLotus.Diagnostic_20261008_191327.txt` contains 396
0152 events: 33 complete six-word snapshots, all identical from 19:13:31 to
19:13:47. Result is `600d0000`, CPU count 138,300, video count 143,760,
sound count 2,176, peripheral count 10,398 and last acknowledged CPU address
`03800188` (`ldr r7,[r1]` in the RAM heartbeat). The initial memory/peripheral
setup reached success, but sustained execution is not established. The APF
bridge/logger remained responsive. No new display description was supplied
for this run; retain the user's corrected 0.1.3 observation separately.

Original log SHA-256:
`e284cb71c15937cd3397af0ec15e3c235a1a6f825142bd0a58a012923dc454a5`.
The original trace and all decoded bursts are retained under ignored
`build/hardware-logs`; compact evidence is in `hardware-evidence.json`.
Frozen exported counters do not distinguish stopped clocks, stalled bus
execution or a stale coherent mailbox. No such cause is claimed yet.

Version 0.1.5 adds independent divided-clock and acknowledgement liveness,
plus reset/MEMC/arbiter/PSRAM flags, captured directly in the bridge domain.
They bypass the six-word status mailbox and do not access guest memory. A
directed simulation distinguishes stopped ACKs with clocks live from stopped
generated clocks with bridge flags still updating, including reset while
clocks are stopped. The eight-word logging test also checks burst capture,
delayed host completion, Ready priority and reset/reload cancellation.
Actual build and installation results are recorded separately when complete.

While investigating, a directed slow-memory flyback test reproduced a separate
concrete defect: MEMC canceled an outstanding video DMA burst as flyback began,
then treated its returning data as a new CPU cache line. The test returned
`76543210` from the framebuffer instead of the CPU's `cafe0000` RAM word.
The corrected generated MEMC derivative retains DMA ownership until all four
ACKs complete, resets video/cursor pointers after draining and blocks new
video/cursor grants during flyback. No preserved upstream file is changed.
Sixteen video/cursor physical-read and ACK boundary cases pass, with correct
CPU cache miss and hit data. The simulation-only legacy switch reproduces the
failure with an expected simulator exit 1. This defect may contribute to the
Pocket fault; hardware confirmation remains required.

The instrumentation-only interim build completed after a fitter access
violation and an unchanged mapped-design retry. Its bitstream was not installed.
The final 0.1.5 build was restarted from synthesis after the MEMC change and
both complete chipset/APF simulations were restarted. Earlier build attempts
and their exact source digests remain archived; results are not mixed.

The final fixed 0.1.5 completed all five Quartus stages at exit 0: 6,398 ALMs,
7,936 registers and a 1,041,148-byte RBF. Reported timing/skew checks pass in
four models (worst setup 0.765 ns, worst hold 0.098 ns); full external board
timing remains unqualified. Fourteen simulation/elaboration checks pass, and
the original flyback path produces its expected failure. Complete chipset
execution reaches `600d0010` with zero qualified pixel FIFO underflows; the
complete APF run exports 112 events with live independent clock/reset probes.
Raw RBF SHA-256:
`16f154a112b06d4ca4edd4d36da7c2f30dfc11716b11c3160b75f3f57fdda7b8`.
Verified ZIP SHA-256:
`29003c92faec7c05d2a28fbf554db2b8637b6bb3532b74f7834ea7b1275c08e6`.
Direct installation changed only bitstream.rbf_r, core.json and info.txt;
all twelve installed hashes match. Physical repair acceptance is pending.

## Physical retry: 0.1.5 sustains execution and coloured bars

The user reported an initial white horizontal bar at the bottom, a continuous
tone and coloured striped bars on screen; the reply confirmed that the bars
remain visible. The user reiterated that the tone is continuous in this run.
The 55,181-byte trace `PocketLotus.Diagnostic_20261008_195020.txt` contains 624
events forming 39 complete eight-word bursts. All 39 have success `600d0000`
and strictly increasing CPU/video/sound/peripheral counts. Independent system
and pixel clock probes also advance; PLL locked/ready remain true and CPU/pixel
reset false. The freeze present in 0.1.4 did not recur.

Trace SHA-256:
`e6a0b5156da59c7922212205835260f92e3b1efc7690aa4ff18560ef09c9855d`.
CPU ACKs increase 227,273→8,550,237, video 247,532→10,194,688,
sound 3,780→155,060 and peripheral 18,135→741,871. These are transaction
observations, not instruction retirement or measured clock frequencies.
The regression demonstrates the DMA/cache defect separately; the faulty
physical data return was not directly captured.

No A input was captured in this trace. A separate five-second hold of the
rightmost Pocket face button was requested, followed by a new log readback.
Sustained coloured display and continuous tone are user observations; physical
geometry/frame rate, stereo/sample fidelity and external board timing remain
unqualified. RISC OS, protected JFD and Lotus remain untested.

## Physical input retry: A press and release verified

The user completed the explicit hold after identifying the rightmost face
button. `PocketLotus.Diagnostic_20261008_195617.txt` is 37,261 bytes and contains
400 events: 25 complete eight-word bursts, with no parser errors. Results are
three `600d0000` snapshots before the press, fifteen `600d0010` while A bit 4
is held, then seven `600d0000` after release. CPU/video/sound/peripheral
acknowledgements strictly increase throughout. The physical input path through
APF PAD, the coherent key mailbox and ARM diagnostic heartbeat is verified.
Other keys and the Archimedes keyboard protocol remain untested.

Trace SHA-256:
`79561798ea51663a8720696a511f63323300d91303b8a19a9844284c525eff9e`.
The original log and decoded bursts remain under ignored `build/hardware-logs`.
Diagnostic execution and A input now have device-log evidence; persistent
coloured bars and continuous tone have user-report evidence. Physical board
timing/geometry/frame rate and stereo fidelity remain separate open checks.
The next software gate is RISC OS boot with separately supplied dependencies,
before protected JFD and Lotus hardware gameplay/audio/video verification.

Install by merging the replacement ZIP's `Cores`, `Platforms` and `Assets`
directories into the SD root, replacing this core's files. Preserve other
cores, assets, settings and saves. Select **ARM diagnostic / diagnostic.bin**
if the asset browser appears. The next gate is a successful diagnostic load
and observed 320x256 nominal 50 Hz VIDC output, stereo and input; external APF
board timing also remains unqualified. RISC OS, protected JFD and Lotus
hardware acceptance remain later, untested gates.
