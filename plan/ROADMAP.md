# PocketLotus roadmap

Started 22 November 2026, when the project moved from a hardware Archimedes core to a static recompilation on openfpgaOS. Architecture and findings are in [docs/PORT_ARCHITECTURE.md](../docs/PORT_ARCHITECTURE.md). The other files in this directory belong to the retired hardware route.

Each milestone ends with something that can be observed. A later milestone is not started on the strength of an earlier one being "mostly" done.

## M0 Unpack and reference run on PC — done 22 November 2026

- Static decryption of the X Lock loader, start-up stub and packed program (`tools/lotus/unpack.py`).
- ARM2 interpreter, machine model and RISC OS call layer (`port/core`), headless runner (`port/host`).
- Observed: Krisalis screen, Lotus title, credits, car screens and the attract-mode race render correctly over 4,000 frames. Music and sound calls were accepted and ignored at that point (sound followed in M4).

## Position on 23 November 2026

M0, M1, M2 and M4 are met on PC. The reference plays the first-disk loop unattended (an autopilot drives races, game over returns to the menu and the next game starts), with music and sound effects. Translated code matches the interpreter frame for frame and sample for sample over 40,000 frames. M3 is done up to the device: the core builds and packages, runs in the SDK desktop shim, and runs the scripted session to the end in the SDK's simulator of the Pocket processor, at about 1.4 million estimated cycles per race frame against 2 million available. The core runs on a Pocket (M3 step 5). Fixes for the sound crackle and the race-view flicker seen on the first device run are built and copied to the card but not yet confirmed on the device. Two-console play over the link cable (M7) works between two desktop instances, each showing its own player full screen.

On 24 November 2026: name and password entry with the pad, saving of the high score table, names, password and options to save slot 0, and the horizon flicker fixed (raster band timing, see [PORT_ARCHITECTURE.md](../docs/PORT_ARCHITECTURE.md)). Name entry, saving and the race picture are confirmed on a Pocket; the Pocket shows the framebuffer 2 pixels right of where it is written, which the race picture now allows for. The one-step builder (`build_core.py`, `Build-PocketLotus2.cmd`) reproduces the tested core from the disk images, and version 1.0 is released with source and the core's game-free files.

## M1 Complete reference behaviour on PC

The reference has to play the whole game before it can judge a translation.

1. Input: pad to `Joystick_Read` and the keys the menus need. Scripted input for repeatable runs. **Done.** The game reads the keyboard with `OS_Byte 121`; internal key 8 is fire, 50/51 down/up, 66/97 right/left, 113 skips the attract sequence.
2. Play through: menus, a full race on each disk, disk 2 loading, game over, passwords. **Done for disk 1**: the autopilot (`--autodrive`) finishes races on the forest and night courses, reaches game over and restarts. Not reached: disk 2 courses (the autopilot does not qualify far enough) and password entry.
3. Fidelity checks against a known-good Archimedes emulator: screen geometry, palette changes within a frame, speed. The black strip at the left of the race view is the game's own: it clears the leftmost word of every race line each frame to hide the scroll seam (`&16E64`). While racing, the renderer moves the picture 4 pixels left so that the black edge is split evenly between both sides.
4. Deterministic record and replay, with a per-frame state hash.
5. Execution coverage and indirect-jump target log for the recompiler.
6. Optional interactive window through the SDK's desktop build.

Exit: a scripted run that completes a race with matching frames on repeat, and a coverage file.

## M2 Recompiler

1. Code discovery: static descent plus M1 coverage; report of code, data and unknown bytes.
2. ARM to C translation of blocks, including PSR-in-R15 idioms, the PC+12 call convention, conditional execution and flag handling.
3. Dispatch for indirect jumps, interpreter fallback for untranslated addresses, detection of writes into translated code.
4. Interrupt delivery and cycle accounting at block boundaries, equivalent to the interpreter's.
5. Lockstep validation against the interpreter on PC, then the M1 scripted run on translated code alone.

Exit: the M1 run produces identical frame hashes with translated code, and the fallback counter is zero or explained.

State: met over 40,000 autopiloted frames including several races, game over and restart (the fallback is the one run-time-patched word at `&DF54`). Disk 2 is not covered yet; code first reached on a Pocket falls back to the interpreter. Wait loops are shortened exactly in translated code. Translation quality work that remains: returns and calls currently go through the chunk `switch`, and flags are computed eagerly; both are candidates once Pocket speed is measured.

## M3 First light on the Pocket

1. Working SDK checkout with runtime files, RISC-V toolchain and `make`. **Done** (see [PORT_BUILD.md](../docs/PORT_BUILD.md)).
2. `port/of`: video mode, input, asset pack loading through a data slot, frame pacing. **Done**, verified in the SDK desktop shim and the SDK simulator. Pacing: the 50 Hz flip when the display really runs at 50 Hz, otherwise a 20 ms clock (the desktop shim flips at 60 Hz, which had made the game and music run fast).
3. Asset pack builder from the user's disks. **Done** (`tools/lotus/pack.py`).
4. Custom core package through the SDK so that the Pocket menu entry starts the game. **Built**, not yet run.
5. Run on a Pocket: copy `build/deps/openfpgaSDK/build/pocket/lotus2` to the SD card, check picture, controls and the frame time the program prints. **Done**: the core appears under Computer and plays (the platform ID must be lowercase, `lotus2`).

Unknowns that only the device answers: whether the 320x256 RGB565 source mode and 50 Hz timing are accepted by this OS build, loading time of the 1.3 MB pack, and real speed (the simulator estimate is 1.4 M cycles per race frame, 68 % of the budget; the display conversion is about 0.4 M of that). The program needs about 35 MiB of the 54 MiB application memory.

Exit: title sequence visible on a Pocket.

## M4 Audio

1. Sound effects: call the game's channel handler each buffer period, convert VIDC logarithmic samples, stream through `of_audio`. **Done.**
2. Music: `MusicModule2` does not touch hardware, so it runs as guest code and is recompiled with the game. **Done.**

Exit: title music and race sound effects on PC (met), then on the Pocket.

## M5 Speed and fidelity on hardware

Full 50 Hz with translated code, measured. Profiling, hot paths in BRAM, video conversion cost, raster palette effects, controls feel, both disks.

Exit: a complete race on a Pocket at full speed with sound.

## M6 Packaging

User-side build from the user's own disks, core ZIP layout, documentation, licence notices, audit that no game content is in the published tree.

State: done for version 1.0 (24 November 2026). The builder makes the core from the disk images or the JASPP package and checks every intermediate result; the release holds the source and a zip of the core files that contain no game. The platform art (the title logo) is published in the README and the release by the author's decision.

## M7 Two Pockets over the link cable

The Archimedes version has a split-screen two-player mode but no link play. Both consoles run that mode in lockstep, exchanging only pad input (`port/of/link.c`), and each draws only its own player's view at full height (`port/core/view.c`).

1. Lockstep protocol with input delay, handshake, periodic state-hash comparison, fallback to solo play. **Done**, tested between two desktop instances over TCP.
2. Own full-screen view per console, game logic unchanged, drawing time fixed so both consoles stay in step. **Done**: identical lockstep hashes over a 4,500-frame race for player 1's view, player 2's view and the two-view reference.
3. Run on two Pockets with a link cable: connection, latency of the 3-frame input delay, sound and speed on both.

Exit: a complete two-player race on two linked Pockets.

## M8 After release: making the core known

Researched 23 November 2026. The core cannot be offered as a download, because a built core contains game content. The community core list and the updaters that read it (pupdate, Pocket Sync) expect a downloadable release, so players have to be pointed at the repository and the build guide instead.

Before announcing:

1. GitHub topics on the repository: `analogue-pocket`, `openfpga`, `openfpgaos`, `static-recompilation`.
2. A screenshot or GIF near the top of the README (title screen, a race, two linked Pockets).
3. A tagged v1.0 release with source and tools only, whose notes say that the core is built from the user's own disks.
4. Wording that cannot be read as distributing Lotus Turbo Challenge 2; every post links to the README's game content section.
5. Every post names what is untested: link play on two real Pockets and the disk 2 courses.

Where to announce:

1. openFPGA core list ([openfpga-library/analogue-pocket](https://github.com/openfpga-library/analogue-pocket), which the old cores-inventory link now opens). Open an issue first to ask how a build-it-yourself core should be listed, then use the [New Core form](https://github.com/openfpga-library/analogue-pocket/issues/new?template=new-core.yml). An entry without a download may confuse the updaters.
2. openfpgaOS developers: an issue or discussion on [openfpgaSDK](https://github.com/openfpgaOS/openfpgaSDK) presenting the port. The [openfpgaOS organisation](https://github.com/openfpgaOS) hosts other game ports (Doom, Quake, Diablo, ScummVM), and no Discord or forum was found for it.
3. FPGA Gaming Discord, which Pocket tool developers such as [Pocket Sync](https://github.com/neil-morrison44/pocket-sync) point users to.
4. Reddit r/AnaloguePocket, with a short video of a race and of linked play.
5. News tips to sites that cover new Pocket cores: [Time Extension](https://timeextension.com/guides/all-analogue-pocket-openfpga-cores-and-where-to-download-them), [RetroRGB](https://www.retrorgb.com/), [Retro Game Corps](https://retrogamecorps.com/category/fpga/).
6. Acorn communities: StarDot forums, RISC OS Open forums, r/acorn.
7. Technical audiences: a write-up of the recompiler and its frame-exact verification, based on [PORT_ARCHITECTURE.md](../docs/PORT_ARCHITECTURE.md), posted as a Show HN and shared with static-recompilation projects.

Exit: the core is listed or linked on the core list and announced in the Pocket, openfpgaOS and Acorn communities.

State on 24 November 2026: the preparation steps are done (topics, title and race screenshots in the README, v1.0 release, wording). Drafts for every post are in [ANNOUNCEMENTS.md](ANNOUNCEMENTS.md); nothing has been posted yet. The single release asset is the game-free zip, which an updater would install as if it were a working core, so the core list question comes first.

## Risks

| Risk | Handling |
| --- | --- |
| Code modified at run time | Write detection in M2; interpreter fallback for affected ranges |
| Timing loops that depend on ARM2 speed | Cycle budget is kept per scanline in both interpreter and translated code |
| Music module pokes hardware directly | Ruled out: it uses only the sound system interface |
| 320x256 on a 320x240 panel | SDK scales a 320x256 source; the race view appears to use about 200 lines, so a crop option is plausible |
| Translated program is derived game content | Built locally from the user's disks, never distributed |
| SDK changes | SDK commit pinned in `analysis/reference-lock.json`; working checkout recorded in the build notes |
