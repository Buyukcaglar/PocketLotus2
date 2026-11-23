# PocketLotus2

PocketLotus2 brings the Acorn Archimedes version of **Lotus Turbo Challenge 2** (Krisalis Software, 1992) to the Analogue Pocket. It is a **static recompilation**: the original ARM program is translated to C and rebuilt for the RISC-V processor of [openfpgaOS](https://github.com/openfpgaOS/openfpgaSDK), with a small runtime standing in for the parts of RISC OS and the Archimedes hardware the game uses. It is packaged as a Pocket core that starts the game directly.

**No game content is included.** You build the core from your own copy of the original disks. See [Game content](#game-content).

## Features

- The complete first-disk game: title sequence with music, car screens, options menu, races with engine and effects sound, game over and restart.
- Original speed: the game runs at its native 50 Hz, with music and sound mixed at 48 kHz.
- Two players on one Pocket with a second controller on the Dock, using the game's own split screen.
- **Two players on two Pockets over the link cable**, a mode the Archimedes original never had. Both consoles run the game in lockstep and exchange only controller input, and each shows its own car full screen.
- Translated code that matches the original program exactly. Over 40,000 frames of automated play the recompiled game produces the same machine state and sound as an ARM interpreter running the original code, frame for frame.

## Status

Version 1.0. It runs on the Analogue Pocket. Not yet tested: link-cable play between two real Pockets (it is tested between two desktop instances), and the courses on the second disk.

| Area | State |
| --- | --- |
| Loader decryption | Done statically; the protected disk sector is not needed |
| ARM to C recompiler | 18,818 game and 1,728 music instructions translated; matches the interpreter frame for frame |
| Pocket core | Runs on the device; about 1.4 M of the 2 M processor cycles per frame in a one-player race, about 1.6 M in linked play (SDK simulator estimate) |
| Input | Pad 1 is player 1 and pad 2 is player 2; two Pockets over the link cable |
| Audio | Original music module, run as recompiled code, plus race sound |

## Controls

| Pocket | Game |
| --- | --- |
| D-pad | Steer; move in menus |
| A or B | Fire / accelerate |
| R / L | Gear up / down (the default gearbox is manual) |
| X or Start | Skip the attract sequence |
| Select | Escape |

The player name and password boxes in the options menu expect a keyboard. On the Pocket, the next fire or d-pad press leaves the box with its contents unchanged.

**Link cable play:** connect two Pockets. Hold **L** while starting the core on one Pocket (host, player 1) and **R** on the other (joins, player 2); each waits up to 30 seconds for the other. In the options menu the host chooses two players and starts the game. If the link drops, play continues alone.

## Building

You need your own disk images of the Archimedes release, *Lotus Turbo Challenge 2 (1992) (Krisalis Software)*, disks F1023201 and F1023202, in JFD format. Put them in a `Lotus/` folder at the root of the repository. Git ignores that folder.

The full commands, requirements and test procedures are in [docs/PORT_BUILD.md](docs/PORT_BUILD.md). In outline:

1. `python analysis/media/inspect_media.py`: reads the disk images and extracts their files.
2. `python tools/lotus/unpack.py`: decrypts the loader and the program.
3. `sh port/host/build.sh`, then a few scripted runs of the PC runner: these record which code the game executes.
4. `python tools/lotus/recomp.py`: translates the program to C, then verifies the translation against the interpreter.
5. `python tools/lotus/pack.py`: builds the asset pack `lotus2.dat`.
6. `sh port/of/build.sh`: builds the Pocket core with the openfpgaSDK.
7. Copy `Assets`, `Cores` and `Platforms` from `build/deps/openfpgaSDK/build/pocket/lotus2` to the root of the Pocket's SD card.

The core appears under the **openfpgaOS** category as **PocketLotus2**.

## How it works

- [docs/PORT_ARCHITECTURE.md](docs/PORT_ARCHITECTURE.md) explains the recompiler, the machine and RISC OS model, video, sound and the link protocol, and records what was learned about the game.
- [plan/ROADMAP.md](plan/ROADMAP.md) has the milestones and the current position.

| Path | Contents |
| --- | --- |
| `port/core` | Portable C runtime: ARM2 interpreter, machine model, RISC OS calls, runner for translated code, own-view drawing for linked play |
| `port/of` | openfpgaOS front end, link cable protocol, Pocket build script, desktop self-test, simulator profile |
| `port/host` | PC runner: dumps frames, sound and state hashes, scripted input, autopilot |
| `port/bench` | RISC-V instruction-count benchmark under QEMU |
| `tools/lotus` | Unpacker, recompiler, disassembler, asset packer and helpers |
| `analysis` | Disk and package analysis scripts and their evidence (hashes and metadata only) |
| `docs`, `plan` | Documentation and planning |

## Game content

Lotus Turbo Challenge 2 is a commercial game, and its rights belong to their owners. This repository contains only original code, tools and documentation. Neither the repository nor any release contains the game program, its assets or anything derived from them. That covers the decrypted program, the generated C, the built `lotus2.elf` and the asset pack `lotus2.dat`. All of these are produced on your machine from your own disks, under `build/`, which Git ignores. Do not share a built core.

This project is not affiliated with or endorsed by the rights holders of Lotus Turbo Challenge 2, by Analogue or by the openfpgaOS project.

## Legacy hardware core route

Until November 2026 the project built an Archimedes chipset core (ARM26, MEMC, VIDC and IOC from Archie_MiSTer) in a Pocket APF shell. It reached a diagnostic bitstream that ran on a Pocket, but stopped before RISC OS booted. That work lives in `rtl`, `sim`, `quartus`, `apf`, `firmware`, the top-level `tools/*.py` scripts and the two manifests. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/BUILD.md](docs/BUILD.md) and the other files in `plan` describe it. The recompilation route does not use any of it. It is kept for reference and is not maintained. Two vendored Amber wrappers without licence headers (`sram_byte_en.v`, `sram_line_en.v`) are not published, so that route does not build from this repository alone.

## Licence

The project's own code is licensed under the GNU General Public License v3.0 or later ([LICENSE](LICENSE)). Vendored third-party sources under `rtl/vendor` keep their own notices; see [LICENSES/README.md](LICENSES/README.md).

## Credits

- [openfpgaOS / openfpgaSDK](https://github.com/openfpgaOS/openfpgaSDK): the Pocket operating system, SDK, desktop shim and simulator this core builds on.
- [Capstone](https://www.capstone-engine.org/): disassembly in the analysis tools.
- Archie_MiSTer, Amber (Conor Santifort) and Stephen J. Leary's Archimedes chipset RTL: the legacy hardware route.
- Krisalis Software, for the original game.

Author: Onur Buyukcaglar.
