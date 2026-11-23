# Building and running the port

Commands for the recompilation route. Run them from the repository root in a POSIX shell (Git Bash works). The hardware-route commands are in [BUILD.md](BUILD.md) and are not needed.

## Requirements

| Need | Present on the development machine |
| --- | --- |
| Python 3 with `capstone` (disassembly only) | Yes |
| A C99 compiler for the PC runner | Yes, MSYS2 UCRT64 gcc at `C:/msys64/ucrt64/bin` |
| The user's disk 1 and disk 2 files extracted under `analysis/media/F1023201/extracted` and `F1023202/extracted` | Yes, from the October analysis (`analysis/media/inspect_media.py`) |
| RISC-V toolchain and `make` | Yes, MSYS2 packages `mingw-w64-ucrt-x86_64-riscv64-unknown-elf-gcc`, `-binutils`, `-newlib` (gcc 16.1.0) |
| Full openfpgaSDK checkout with `runtime/` | Yes, `build/deps/openfpgaSDK` at commit `91864a6` |
| SDL2 for the desktop self-test | Yes, MSYS2 package `mingw-w64-ucrt-x86_64-SDL2` |
| QEMU for the instruction-count benchmark | Yes, MSYS2 package `mingw-w64-ucrt-x86_64-qemu` |
| POSIX gcc for the SDK simulator (`tools/qsim` needs `sys/mman.h`) | Yes, MSYS2 package `gcc` at `C:/msys64/usr/bin` |

The checkout in `references/openfpgaSDK` is a sparse, source-only snapshot for reading. The working checkout is `build/deps/openfpgaSDK`. Clone it with `git -c core.autocrlf=false clone`: with line-ending conversion on, the bundled musl libraries are corrupted and linking fails with "linker script file appears multiple times".

## Unpack the program

```sh
python tools/lotus/unpack.py
```

Writes `stub_70000.bin`, `packed_8000.bin`, `loader_stage2.bin` and `unpack.json` to `build/lotus`. The script checks the `Loader` hash before doing anything.

## Build and run the PC runner

```sh
sh port/host/build.sh
./build/host/lotus_host --frames 4000 --every 250 --out build/lotus/frames
python tools/lotus/ppm2png.py build/lotus/frames/*.ppm
```

Options: `--input SCRIPT` timed input (below), `--frames N` frames to run, `--every N` dump interval, `--out DIR` existing output directory, `--trace` log OS and hardware accesses, `--hash FILE` write one state hash per frame, `--dump-app FILE` save application memory at the end, `--lenient` continue past unknown non-X SWIs.

`build.sh` produces three programs: `lotus_host` (interpreter), `lotus_host_cov` (interpreter with coverage and self-modification reports, writes `build/lotus/coverage.bin`) and, once generated code exists, `lotus_host_rc`.

The first run also writes `build/lotus/game_image.bin`, the expanded program from `&8000` to `&70000`, captured when the start-up stub hands over.

## Scripted input

`--input` takes space-separated events `FRAME:kN` (key N down), `FRAME:uN` (key up) and `FRAME:pMASK` (joystick bits: 1 up, 2 down, 4 left, 8 right, 16 fire). Keys are RISC OS internal key numbers: 8 fire, 50 down, 51 up, 66 right, 97 left, 113 skip. This run opens the options menu, starts a game and drives:

```sh
RACE="450:k8 470:u8 600:k50 610:u50 700:k8 720:u8 1300:k8 2000:k97 2040:u97 2400:k66 2440:u66"
./build/host/lotus_host --frames 4200 --every 300 --out build/lotus/race --input "$RACE"
```

Sound: `--wav FILE` writes everything the game played as a 48 kHz stereo WAV. `python tools/lotus/wavstat.py FILE` prints level and pitch summaries per second.

Autopilot: `--autodrive FRAME` takes over from that frame. In a race it holds fire (accelerate), changes up and steers towards the middle of the road; elsewhere it presses down and fire every 10 s, which starts a new game from the options menu after game over. With the menu part of the script above it plays unattended:

```sh
./build/host/lotus_host --frames 40000 --every 1000 --out build/lotus/long --input "450:k8 470:u8 600:k50 610:u50 700:k8 720:u8" --autodrive 1300
```

## Recompile and verify

```sh
./build/host/lotus_host_cov --frames 6000 --out build/lotus/frames   # coverage.bin
python tools/lotus/recomp.py                                          # build/lotus/gen/lotus_gen.c
sh port/host/build.sh                                                 # adds lotus_host_rc
./build/host/lotus_host_rc --engine reference  --frames 6000 --out build/lotus/frames --hash build/lotus/hash_reference.txt
./build/host/lotus_host_rc --engine translated --frames 6000 --out build/lotus/frames --hash build/lotus/hash_translated.txt
cmp build/lotus/hash_reference.txt build/lotus/hash_translated.txt
```

`--engine translated` runs the generated C with interpreter fallback and prints the number of fallback steps. Entry addresses of fallbacks go to `build/lotus/leaders_seen.txt`; running `recomp.py` again merges them into `leaders_extra.txt` and translates from them. Repeat until the count stops falling. `--engine reference` is the interpreter with the same block-leader map, which is what makes the two hash files comparable; both must be regenerated after every recompile.

Coverage accumulates across `lotus_host_cov` runs, so run it once per scripted session before recompiling. Pass the same `--input` to both engines when comparing hashes.

## Build the Pocket core

One-time, in `build/deps/openfpgaSDK`:

```sh
bash scripts/customize.sh --batch --name "PocketLotus2" --short lotus2 --author "Onur Buyukcaglar" --platform lotus2 --version 1.0 --variant os25
```

Then, from the repository root:

```sh
python tools/lotus/pack.py     # build/lotus/lotus2.dat, the asset pack
sh port/of/build.sh            # installs sources into the SDK src/lotus2 and builds
```

`build.sh` copies `port/core`, `port/of/main.c`, the generated C and the pack into the SDK custom-core directory, adds the pack as data slot 4 and writes `lotus2.ini`, then runs the SDK build with `USE_SDK_CONTAINER=0` (host toolchain instead of Docker). The result is `build/deps/openfpgaSDK/build/pocket/lotus2`; copy its `Assets`, `Cores` and `Platforms` folders to the root of the Pocket SD card. It contains game content and is for personal use only.

Pocket controls: D-pad steers and moves in menus, A or B is fire and accelerate, R and L change gear up and down (the default gearbox is manual), X or Start skips the attract sequence, Select is Escape. A second pad on the dock plays as player 2. The player name and password boxes in the options menu take typed text, which the Pocket cannot type: the next fire or d-pad press leaves the box unchanged (it reads as Return).

Link cable play: connect two Pockets, hold **L** on one while starting the core (host, player 1) and **R** on the other (joins, player 2). Each waits up to 30 s for the other. In the options menu the host moves up to PLAYERS, presses fire to choose two players, then starts the game. In the race each console shows its own car full screen: the host player 1, the joining console player 2. If the link drops, play continues alone.

Desktop test of the link (two instances talking over localhost):

```sh
sh port/of/test_pc.sh 10
cd build/lotus && mkdir -p linkA linkB && cp pc/app_pc.exe pc/lotus2.dat linkA/ && cp pc/app_pc.exe pc/lotus2.dat linkB/
(cd linkA && LOTUS_LINK=host LOTUS_SHOT=1800 ./app_pc.exe bench 2000) & (cd linkB && LOTUS_LINK=join LOTUS_SHOT=1800 ./app_pc.exe bench 2000)
```

In a linked bench run the host selects two players and drives player 1 and the joining instance drives player 2. `linkA/lotus_shot.ppm` must show the red car (player 1) full screen, `linkB/lotus_shot.ppm` the white car (player 2), and neither instance may print a "games differ" line.

The own views can also be checked without a link: run `lotus_host` with the same input script and `--view 1`, `--view 2` and `--view 3` (both views, same timing) with `--lockstep-hash FILE`; the three hash files must be identical, and the scores in the `--view 3` split screen must match the own views.

## Run the Pocket program in the SDK simulator

`tools/qsim` in the SDK checkout runs the production ELF on a model of the Pocket processor and memory and estimates cycles. Build it once with the POSIX compiler, then run the project's profile in `port/of/qsim/lotus2`:

```sh
cd build/deps/openfpgaSDK/tools/qsim
PATH=/c/msys64/usr/bin:$PATH make CC=/usr/bin/gcc qsim
PATH=/c/msys64/usr/bin:$PATH ./qsim ../../.obj/lotus2/app.elf --app ../../../../../port/of/qsim/lotus2/lotus2.app     --data-dir ../../../../lotus --out ../../../../qsim/race --args "bench 3000" --profile
```

`bench N` makes the program play a built-in session for N frames without waiting for the display and print `BENCH DONE`; the slot registry and clock are not used in that mode because the simulator does not provide them. Results on 23 November 2026: 3,000 frames (attract, menu, 1,700 race frames) take 4.85 G estimated cycles; the difference against a 1,600-frame run gives 1.36 M cycles per race frame, of which 0.40 M is the display conversion. The budget at 100 MHz and 50 Hz is 2 M.

## Instruction-count benchmark

```sh
BENCH_DEFS=-DBENCH_FRAMES=3000 sh port/bench/run.sh
```

Builds the game with the Pocket compiler flags for QEMU's bare RISC-V machine and prints instructions per frame for game and display. It is slow (tens of minutes for 3,000 frames); the simulator above gives the same split with a timing model.

## Desktop self-test of the front end

```sh
sh port/of/test_pc.sh 1500     # frames to run; writes build/lotus/pc/lotus_shot.png
```

Builds `port/of/main.c` against the SDK SDL2 shim and runs it in a window. Started by hand from `build/lotus/pc` without `LOTUS_SHOT` set, `app_pc` is playable: arrow keys, Z or X for fire, A to skip.

## Inspect code

```sh
python tools/lotus/disasm.py 12830 12860
```

Disassembles a range of the expanded image. Instructions with the never condition are shown as `nop (NV)`; the converted code uses them as padding after calls.

## Outputs are private

Everything under `build/lotus` is derived from the game and must not be published.
