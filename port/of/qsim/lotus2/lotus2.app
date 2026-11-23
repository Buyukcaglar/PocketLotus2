# qsim app profile for the Lotus core (see the SDK's tools/qsim/README.md).
#   QSIM_APP=<repo>/port/of/qsim/lotus2 QSIM_DATA_DIR=<repo>/build/lotus ./run.sh lotus2.elf out race
name         = Lotus2
elf_name     = lotus2.elf
default_args = bench 3000
result_line  = ^BENCH DONE ([0-9]+) frames
error_line   = PocketLotus:
slot = 1  os.bin      stub:127848
slot = 2  lotus2.ini  config:lotus2.ini.in
slot = 3  lotus2.elf  stub:1200000
slot = 4  lotus2.dat  data:lotus2.dat
