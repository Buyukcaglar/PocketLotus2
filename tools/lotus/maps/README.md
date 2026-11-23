# Recompiler maps

Inputs that make `tools/lotus/recomp.py` reproduce the tested translation from a
user's own game files, without the long recorded play sessions that produced them.
They hold addresses and flags only, no game code or data.

| File | Contents |
| --- | --- |
| `coverage.bin` | One byte per word of the program from &8000: bit 0 executed, bit 1 written at run time, accumulated over the reference sessions |
| `coverage_mus.bin` | The same for the music module at &1A00000 |
| `leaders_extra.txt` | Indirect jump targets found at run time, one hex address per line |
| `expected.json` | SHA-256 of the supported disk images and of the build's intermediate results, which `build_core.py` checks |

Regenerate them after changing the recompiler or the runtime's code hooks: run
the coverage sessions in `docs/PORT_BUILD.md`, then copy the three map files from
`build/lotus` and update the hashes in `expected.json`.
