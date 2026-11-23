#!/usr/bin/env python3
"""Finish the SDK's generated core package (dist/lotus2) for PocketLotus2.

scripts/customize.sh writes the package from the SDK templates. This adds what
the templates do not know: the asset pack as data slot 4 of the instance file,
the menu category and manufacturer of the platform, and the project URL in
core.json. Running it again changes nothing.

Usage: package_meta.py SDK_DIST_DIR      (for example build/deps/openfpgaSDK/dist/lotus2)
"""
import json
import sys
from pathlib import Path

CATEGORY = "openfpgaOS"
MANUFACTURER = "Krisalis"
URL = "https://github.com/Buyukcaglar/PocketLotus2"


def edit_json(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8", newline="\n")


def add_pack_slot(data):
    slots = data["instance"]["data_slots"]
    if not any(s.get("filename") == "lotus2.dat" for s in slots):
        slots.append({"id": 4, "filename": "lotus2.dat"})


def set_platform(data):
    data["platform"]["category"] = CATEGORY
    data["platform"]["manufacturer"] = MANUFACTURER


def set_url(data):
    data["core"]["metadata"]["url"] = URL


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    dist = Path(sys.argv[1])
    instances = list(dist.glob("Assets/*/*/lotus2.json"))
    cores = list(dist.glob("Cores/*/core.json"))
    platform = dist / "Platforms" / "lotus2.json"
    if len(instances) != 1 or len(cores) != 1 or not platform.exists():
        raise SystemExit(f"{dist}: not a generated lotus2 core package (run scripts/customize.sh first)")
    edit_json(instances[0], add_pack_slot)
    edit_json(platform, set_platform)
    edit_json(cores[0], set_url)


if __name__ == "__main__":
    main()
