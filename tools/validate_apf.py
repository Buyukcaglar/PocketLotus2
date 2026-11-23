"""SPDX-License-Identifier: GPL-3.0-or-later
Validate the small APF profile used by this diagnostic against Analogue's docs.
This is deliberately bounded to our files, not an emulation of the OS parser.
Reject unsupported additions rather than silently claiming to validate them.
"""
import argparse
import json
import re
from pathlib import Path
from hdl_sources import ROOT

DOCS = "https://www.analogue.co/developer/docs/openfpga/"
SOURCES = [DOCS + "core-definition-files/" + name + "-json" for name in
           ("core", "data", "input", "audio", "video", "variants", "interact")]
SOURCES.append(DOCS + "platform-metadata")
SOURCES.append(DOCS + "packaging-a-core")
CORE_FOLDER = "PocketLotus.Diagnostic"


def validate_directory(directory, platform=None, core_folder=CORE_FOLDER):
    errors = []

    def check(ok, message):
        if not ok:
            errors.append(message)

    def string(value, limit, label):
        check(isinstance(value, str) and len(value) <= limit,
              f"{label}: maximum {limit} characters (got {value!r})")

    def integer(value, bits, label):
        try:
            if type(value) is int:
                number = value
            elif isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]+", value):
                number = int(value, 16)
            else:
                raise ValueError()
            check(0 <= number < 2**bits, f"{label}: unsigned {bits}-bit range")
            return number
        except ValueError:
            check(False, f"{label}: integer or hexadecimal string required")
            return -1

    def fields(obj, required, optional, label):
        check(set(required) <= set(obj), f"{label}: missing required fields")
        check(set(obj) <= set(required) | set(optional), f"{label}: unsupported fields")

    files = {}
    for name in ("core", "data", "input", "audio", "video", "variants", "interact"):
        doc = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
        check(set(doc) == {name}, f"{name}: root object")
        files[name] = doc[name]
        check(doc[name].get("magic") == "APF_VER_1", f"{name}: APF magic")
    core = files["core"]
    fields(core, ("magic", "metadata", "framework", "cores"), (), "core")
    metadata = core["metadata"]
    limits = dict(shortname=31, description=63, author=31, url=63, version=31, date_release=10)
    fields(metadata, ("platform_ids", *limits), (), "core.metadata")
    for key, limit in limits.items():
        string(metadata.get(key), limit, "core.metadata." + key)
    expected_folder = metadata["author"] + "." + metadata["shortname"]
    check(expected_folder == core_folder,
          f"core folder: metadata resolves to {expected_folder!r}, installed directory is {core_folder!r}")
    check(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", metadata["date_release"])), "core: date format")
    platforms = metadata["platform_ids"]
    check(isinstance(platforms, list) and len(platforms) <= 4, "core: platform count")
    for pid in platforms:
        check(bool(re.fullmatch(r"[a-z0-9][a-z0-9_]{0,14}", pid)), "core: platform ID")
    framework = core["framework"]
    fields(framework, ("target_product", "version_required", "sleep_supported", "dock", "hardware"), (), "framework")
    check(framework["target_product"] == "Analogue Pocket", "framework: target")
    check(bool(re.fullmatch(r"\d+\.\d+", framework["version_required"])), "framework: version")
    check(type(framework["sleep_supported"]) is bool, "framework: sleep boolean")
    fields(framework["dock"], ("supported", "analog_output"), (), "dock")
    check(framework["dock"]["supported"] is True, "dock: supported must be true")
    check(type(framework["dock"]["analog_output"]) is bool, "dock: analog boolean")
    fields(framework["hardware"], ("link_port", "cartridge_adapter"), (), "hardware")
    check(type(framework["hardware"]["link_port"]) is bool, "hardware: link boolean")
    integer(framework["hardware"]["cartridge_adapter"], 32, "hardware.cartridge_adapter")
    check(1 <= len(core["cores"]) <= 8, "core: bitstream count")
    for bitstream in core["cores"]:
        fields(bitstream, ("id", "filename"), ("name",), "bitstream")
        integer(bitstream["id"], 16, "bitstream.id")
        string(bitstream.get("name", ""), 15, "bitstream.name")
        string(bitstream["filename"], 15, "bitstream.filename")
        check(Path(bitstream["filename"]).name == bitstream["filename"], "bitstream: basename required")
    data = files["data"]
    fields(data, ("magic", "data_slots"), (), "data")
    check(1 <= len(data["data_slots"]) <= 32, "data: slot count")
    ids = []
    for slot in data["data_slots"]:
        fields(slot, ("id", "name", "required", "parameters", "address", "size_maximum", "extensions"), (), "data slot")
        ids.append(integer(slot["id"], 16, "data.id"))
        string(slot["name"], 15, "data.name")
        check(type(slot["required"]) is bool, "data: required boolean")
        integer(slot["parameters"], 32, "data.parameters")
        integer(slot["address"], 32, "data.address")
        integer(slot["size_maximum"], 32, "data.size_maximum")
        check(1 <= len(slot["extensions"]) <= 4, "data: extension count")
        for ext in slot["extensions"]:
            string(ext, 7, "data.extension")
    check(len(ids) == len(set(ids)), "data: duplicate slot IDs")
    check(ids == [0], "diagnostic profile: only implemented slot 0 allowed")
    video = files["video"]
    fields(video, ("magic", "scaler_modes"), (), "video")
    check(1 <= len(video["scaler_modes"]) <= 8, "video: scaler count")
    for mode in video["scaler_modes"]:
        fields(mode, ("width", "height", "aspect_w", "aspect_h", "rotation", "mirror"), (), "scaler")
        for key in ("width", "height", "aspect_w", "aspect_h"):
            check(type(mode[key]) is int and mode[key] > 0, "scaler: positive " + key)
        check(mode["rotation"] in (0, 90, 180, 270), "scaler: rotation")
        check(type(mode["mirror"]) is int and 0 <= mode["mirror"] <= 3, "scaler: mirror")
    inputs = files["input"]
    fields(inputs, ("magic", "controllers"), (), "input")
    check(len(inputs["controllers"]) <= 4, "input: controller count")
    for controller in inputs["controllers"]:
        fields(controller, ("type", "mappings"), (), "controller")
        check(controller["type"] == "default", "controller: type")
        check(len(controller["mappings"]) <= 8, "input: mapping count")
        for mapping in controller["mappings"]:
            fields(mapping, ("id", "name", "key"), (), "mapping")
            integer(mapping["id"], 16, "input.id")
            string(mapping["name"], 19, "input.name")
            check(mapping["key"] in ("pad_btn_a", "pad_btn_b", "pad_btn_x", "pad_btn_y", "pad_trig_l", "pad_trig_r", "pad_btn_start", "pad_btn_select"), "input: keycode")
    fields(files["audio"], ("magic",), (), "audio")
    fields(files["variants"], ("magic", "variant_list"), (), "variants")
    check(files["variants"]["variant_list"] == [], "diagnostic profile: variants must be empty")
    fields(files["interact"], ("magic", "variables"), ("messages",), "interact")
    check(files["interact"]["variables"] == [] and files["interact"].get("messages", []) == [], "diagnostic profile: interact must be empty")
    platform = platform or directory / "platform.json"
    doc = json.loads(platform.read_text(encoding="utf-8"))
    check(set(doc) == {"platform"}, "platform: root object")
    fields(doc["platform"], ("category", "name", "manufacturer", "year"), (), "platform")
    for key in ("category", "name", "manufacturer"):
        string(doc["platform"][key], 31, "platform." + key)
    check(type(doc["platform"]["year"]) is int, "platform: year integer")
    if errors:
        raise ValueError("APF profile validation failed:\n" + "\n".join(errors))
    return dict(passed=True, scope="Documented diagnostic metadata profile; not Analogue OS parser execution", sources=SOURCES)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=ROOT / "apf")
    parser.add_argument("--platform", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_directory(args.directory, args.platform), indent=2))
