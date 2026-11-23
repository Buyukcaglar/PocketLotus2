#!/bin/sh
# Build the Pocket core: install the port sources into the SDK's custom-core
# directory (build/deps/openfpgaSDK/src/lotus2) and run the SDK build there.
# Output: build/deps/openfpgaSDK/build/pocket/lotus2/ (contains game content: never publish).
set -e
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SDK="$ROOT/build/deps/openfpgaSDK"
APP="$SDK/src/lotus2"
export PATH=/c/msys64/ucrt64/bin:/c/msys64/usr/bin:$PATH

[ -d "$APP" ] || { echo "run scripts/customize.sh in the SDK first (see docs/PORT_BUILD.md)"; exit 1; }
[ -f "$ROOT/build/lotus/gen/lotus_gen.c" ] || { echo "run tools/lotus/recomp.py first"; exit 1; }
[ -f "$ROOT/build/lotus/lotus2.dat" ] || { echo "run tools/lotus/pack.py first"; exit 1; }

rm -f "$APP"/*.c "$APP"/*.h
cp "$ROOT"/port/core/*.c "$ROOT"/port/core/*.h "$ROOT/port/of/main.c" "$ROOT/port/of/link.c" "$ROOT/port/of/link.h" "$ROOT/build/lotus/gen/lotus_gen.c" "$APP/"
cp "$ROOT/build/lotus/lotus2.dat" "$APP/"

# data slot 4 carries the asset pack
INST=$(ls "$SDK"/dist/lotus2/Assets/*/*/lotus2.json)
grep -q lotus2.dat "$INST" || sed -i 's|{ "id": 3, "filename": "lotus2.elf" },|&\n            { "id": 4, "filename": "lotus2.dat" },|' "$INST"

# slot 2: the OS reads the application name from this file
COMMON=$(dirname "$(dirname "$INST")")/common
mkdir -p "$COMMON"
printf '[os]
ELF=lotus2.elf
ARGS=
VARIANT=os25
' > "$COMMON/lotus2.ini"

cd "$APP"
make USE_SDK_CONTAINER=0 CFLAGS="-DLOTUS_RECOMP -Wno-unused-label -Wno-unused-parameter -Wno-unused-variable -Wno-unused-but-set-variable -fno-strict-aliasing" "$@"
