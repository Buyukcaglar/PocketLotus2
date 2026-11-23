#!/bin/sh
# Desktop self-test of the Pocket front end through the SDK's SDL2 shim.
# Runs the game for N frames (default 1500) and writes build/lotus/pc/lotus_shot.ppm.
# The SDK's own "make test" does not build on Windows (of_init.c needs sys/auxv.h),
# so the same sources are compiled here without that file.
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SDK="$ROOT/build/deps/openfpgaSDK/src/sdk"
OUT="$ROOT/build/lotus/pc"
export PATH=/c/msys64/ucrt64/bin:/c/msys64/usr/bin:$PATH
mkdir -p "$OUT"
gcc -DOF_PC -DLOTUS_RECOMP -O2 -w -fno-strict-aliasing -I"$SDK/include" -I"$ROOT/port/core" \
    "$ROOT"/port/core/*.c "$ROOT/port/of/main.c" "$ROOT/port/of/link.c" -I"$ROOT/port/of" "$ROOT/build/lotus/gen/lotus_gen.c" "$SDK/pc/of_sdl2.c" \
    $(sdl2-config --cflags) $(sdl2-config --libs | sed 's/-mwindows//') -lm -lws2_32 -o "$OUT/app_pc"
cp "$ROOT/build/lotus/lotus2.dat" "$OUT/"
cd "$OUT"
LOTUS_SHOT=${1:-1500} ./app_pc
python "$ROOT/tools/lotus/ppm2png.py" lotus_shot.ppm
echo "wrote $OUT/lotus_shot.png"
