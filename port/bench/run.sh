#!/bin/sh
# Build the game for RISC-V with the Pocket compiler flags and count the
# instructions it executes per frame under QEMU. See main.c.
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT="$ROOT/build/bench"
export PATH=/c/msys64/ucrt64/bin:/c/msys64/usr/bin:$PATH
mkdir -p "$OUT"
cp "$ROOT/build/lotus/lotus2.dat" "$OUT/"
CC=riscv64-unknown-elf-gcc
FLAGS="${BENCH_DEFS:-} -march=rv32imafc -mabi=ilp32f -O2 -ffunction-sections -fdata-sections -fno-strict-aliasing -w -DLOTUS_RECOMP -I$ROOT/port/core"
cd "$OUT"
for f in "$ROOT"/port/core/*.c "$ROOT/port/bench/main.c" "$ROOT/build/lotus/gen/lotus_gen.c"; do
    o=$(basename "$f" .c).o
    [ "$o" -nt "$f" ] || $CC $FLAGS -c -o "$o" "$f"
done
$CC $FLAGS -c -o crt0.o "$ROOT/port/bench/crt0.S"
$CC $FLAGS -nostartfiles -T "$ROOT/port/bench/link.ld" -Wl,--gc-sections -o bench.elf crt0.o \
    arm26.o machine.o riscos.o sound.o view.o pack.o hybrid.o lotus_gen.o main.o -lc -lm -lgcc
qemu-system-riscv32 -M virt -cpu rv32 -m 256M -bios none -nographic -icount shift=0 -kernel bench.elf
