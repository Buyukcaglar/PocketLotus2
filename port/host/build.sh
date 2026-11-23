#!/bin/sh
# Build the headless host runner with MSYS2 UCRT64 gcc (or any C99 compiler via CC).
set -e
cd "$(dirname "$0")/../.."
[ -d /c/msys64/ucrt64/bin ] && PATH=/c/msys64/ucrt64/bin:$PATH
mkdir -p build/host build/lotus/frames
SRC="port/core/arm26.c port/core/machine.c port/core/riscos.c port/core/sound.c port/core/view.c port/core/save.c port/host/main.c"
${CC:-gcc} -O2 -Wall -Wextra -o build/host/lotus_host $SRC
# analysis build: execution coverage and self-modification reports
${CC:-gcc} -O2 -Wall -Wextra -DARM26_COVERAGE -o build/host/lotus_host_cov $SRC
# translated-code build, when tools/lotus/recomp.py has produced the generated C
if [ -f build/lotus/gen/lotus_gen.c ]; then
    ${CC:-gcc} -O1 -fno-strict-aliasing -Wno-unused-label -Iport/core -c -o build/host/lotus_gen.o build/lotus/gen/lotus_gen.c
    ${CC:-gcc} -O2 -Wall -Wextra -DLOTUS_RECOMP -o build/host/lotus_host_rc $SRC port/core/hybrid.c build/host/lotus_gen.o
fi
