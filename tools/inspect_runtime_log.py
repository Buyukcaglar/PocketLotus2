"""SPDX-License-Identifier: GPL-3.0-or-later
Decode Pocket 0152 marker/data bursts. Keep original trace and incomplete bursts.
This measures exported status, not instruction retirement or electrical timing.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def decode(path, words=6):
    data = path.read_bytes()
    events = re.findall(r"Target: Event Log \(([^)]+)\) \[0x([0-9A-Fa-f]+)\]", data.decode(errors="replace"))
    bursts, errors = [], []
    current, marker = [], None
    for timestamp, hexword in events:
        value = int(hexword, 16)
        if marker is None:
            if value != 0xd1a60000 + len(current):
                errors.append(dict(timestamp=timestamp, expected_marker=len(current), value=hexword))
                current = []
                continue
            marker = len(current)
        else:
            current.append(value)
            marker = None
            if len(current) == words:
                entry=dict(timestamp=timestamp, words=[f"{w:08x}" for w in current],
                           status=dict(zip(("result","cpu_ack_count","video_ack_count",
                                            "sound_ack_count","peripheral_ack_count","last_cpu_address"),current[:6])))
                if words==8:
                    flags=current[7]>>16
                    entry["probe_edge_observations_mod256"]={name:(current[6]>>(i*8))&255
                        for i,name in enumerate(("system_clock","pixel_clock","cpu_ack","video_ack"))}
                    entry["probe_edge_observations_mod256"].update(sound_ack=current[7]&255,peripheral_ack=(current[7]>>8)&255)
                    entry["individually_synchronized_flags"]={name:bool(flags&(1<<bit)) for bit,name in
                        ((15,"pll_locked"),(14,"cpu_reset"),(13,"pixel_reset"),(12,"ready"),
                         (11,"memc_cyc"),(10,"memc_stb"),(9,"memc_write"),(8,"memory_ack"),(7,"psram_busy"),(6,"arbiter_armed"))}
                    entry["individually_synchronized_flags"].update(arbiter_state=(flags>>3)&7,psram_state=flags&7)
                bursts.append(entry)
                current = []
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                event_count=len(events), complete_bursts=len(bursts),
                unique_snapshots=len({tuple(b["words"]) for b in bursts}),
                unique_status_snapshots=len({tuple(b["words"][:6]) for b in bursts}),
                unique_probe_snapshots=len({tuple(b["words"][6:]) for b in bursts}) if words==8 else None,
                bursts=bursts, errors=errors, incomplete_words=current,
                pending_marker=marker,
                scope="Exported status only; frozen values do not distinguish stopped clocks, bus deadlock or stale mailbox")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--words", type=int, choices=(6,8), default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = decode(args.log, args.words)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("bursts", "errors")}, indent=2))


if __name__ == "__main__":
    main()
