#!/usr/bin/env python3
"""PocketLotus2 builder: make the Analogue Pocket core from your own game files.

Give it the original Acorn Archimedes release of Lotus Turbo Challenge 2, as
either of:
  - the two disk images, "Lotus Turbo Challenge 2 (1992) (Krisalis Software)
    F1023201.jfd" and "... F1023202.jfd" (any file names), or
  - the JASPP RISC OS package Lotus-Turbo-Challenge-2_0-1.zip or _0-2.zip.
Files or folders can be given; folders are searched. The default is the folder
"Lotus" next to this script.

The builder checks the files against the known release, extracts and decrypts
the program, translates it to C with the maps in tools/lotus/maps, builds the
asset pack, fetches the openfpgaOS SDK at the tested commit, compiles the core
and writes a folder to copy to the root of the Pocket's SD card. Each
intermediate result is compared with the tested build, so a finished run gives
the same game as the tested one.

Needs: Python 3.8+, a C compiler (gcc or clang), make and bash, and either a
RISC-V toolchain (riscv64-unknown-elf-gcc or riscv64-elf-gcc) or Docker. On
Windows, Build-PocketLotus2.cmd installs all of these through MSYS2 and runs
this script.

Everything built here is derived from the game: it is for your own use only.
Do not share it.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "lotus"
MAPS = ROOT / "tools" / "lotus" / "maps"
MEDIA = ROOT / "analysis" / "media"
SDK = ROOT / "build" / "deps" / "openfpgaSDK"
EXPECTED = json.loads((MAPS / "expected.json").read_text())
PKG_ROOT = "Apps/Games/!LOTUS/"
NEEDED_IN_PACKAGE = ["Loader", "MusMod2", "Krisalis", "DISK1/", "DISK2/"]
CORE_NAME, CORE_AUTHOR, CORE_VERSION = "PocketLotus2", "Buyukcaglar", "1.0"
EXE = ".exe" if os.name == "nt" or sys.platform in ("msys", "cygwin") else ""


class Failure(Exception):
    pass


def step(text):
    print(f"\n== {text}", flush=True)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run(cmd, cwd=ROOT, env=None, quiet=True):
    """Run a command; on failure show its output and stop."""
    shown = " ".join(str(c) for c in cmd)
    full_env = dict(os.environ, **(env or {}))
    if quiet:
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=full_env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        if r.returncode != 0:
            print(r.stdout[-6000:])
            raise Failure(f"command failed ({r.returncode}): {shown}")
        return r.stdout
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=full_env)
    if r.returncode != 0:
        raise Failure(f"command failed ({r.returncode}): {shown}")
    return ""


def check_hash(path, key, what):
    got = sha256(path.read_bytes())
    if got != EXPECTED[key]:
        raise Failure(f"{what} differs from the tested build ({path.name}: {got[:16]}..., expected "
                      f"{EXPECTED[key][:16]}...). Your game files may be a different version.")
    print(f"   {what}: matches the tested build")


# ---- prerequisites -------------------------------------------------------------

def find_tool(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def install_hint():
    system = platform.system()
    if system == "Darwin":
        return ("  xcode-select --install            (C compiler, make)\n"
                "  brew install riscv64-elf-gcc      (or install Docker Desktop instead)")
    if system == "Linux":
        return ("  Debian/Ubuntu: sudo apt install build-essential python3 gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf\n"
                "  Arch:          sudo pacman -S base-devel python riscv64-elf-gcc riscv64-elf-newlib\n"
                "  (or install Docker instead of the RISC-V compiler)")
    return "  Run Build-PocketLotus2.cmd, which installs everything through MSYS2."


def prerequisites(choice):
    missing = []
    cc = os.environ.get("CC") or find_tool("gcc", "cc", "clang")
    if not cc:
        missing.append("a C compiler (gcc or clang)")
    for tool in ("make", "bash"):
        if not find_tool(tool):
            missing.append(tool)
    riscv = find_tool("riscv64-unknown-elf-gcc", "riscv64-elf-gcc")
    docker = find_tool("docker", "podman")
    if choice == "host" and not riscv:
        missing.append("a RISC-V compiler (riscv64-unknown-elf-gcc or riscv64-elf-gcc)")
    elif choice == "docker" and not docker:
        missing.append("Docker")
    elif choice == "auto" and not riscv and not docker:
        missing.append("a RISC-V compiler (riscv64-unknown-elf-gcc or riscv64-elf-gcc) or Docker")
    if missing:
        raise Failure("missing: " + ", ".join(missing) + "\nInstall them, for example:\n" + install_hint())
    container = choice == "docker" or (choice == "auto" and not riscv)
    print(f"   C compiler: {cc}")
    print(f"   RISC-V: {'SDK Docker container' if container else riscv}")
    return cc, container


# ---- game files ---------------------------------------------------------------

def candidate_files(paths):
    for p in paths:
        p = Path(p).expanduser()
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    yield f
        elif p.is_file():
            yield p
        else:
            raise Failure(f"not found: {p}")


def find_game(paths):
    disks, packages = {}, []
    wanted = {h: n for n, h in EXPECTED["disks"].items()}
    for f in candidate_files(paths):
        if f.stat().st_size > 16 << 20:
            continue
        data = f.read_bytes()
        h = sha256(data)
        if h in wanted:
            disks.setdefault(wanted[h], f)
        elif data[:4] == b"PK\x03\x04":
            try:
                z = zipfile.ZipFile(f)
            except zipfile.BadZipFile:
                continue
            names = z.namelist()
            if any(n.startswith(PKG_ROOT) for n in names):
                lacking = [n for n in NEEDED_IN_PACKAGE if not any(x.startswith(PKG_ROOT + n) for x in names)]
                packages.append((f, lacking))
    return disks, packages


def extract_disks(disks):
    """Extract the two disk images with the project's JFD/ADFS reader."""
    spec = importlib.util.spec_from_file_location("inspect_media", MEDIA / "inspect_media.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("F1023201", "F1023202"):
        meta = mod.inspect(disks[name])
        print(f"   {name}: {meta['extracted_file_count']} files")


def extract_package(path):
    """Lay out the package's files the way the disk extraction does."""
    z = zipfile.ZipFile(path)
    n1 = n2 = 0
    for info in z.infolist():
        if info.is_dir() or not info.filename.startswith(PKG_ROOT):
            continue
        rel = info.filename[len(PKG_ROOT):]
        if rel == "F1023201" or "," in rel:
            continue                        # the package's own disk image copy
        if rel.upper().startswith("DISK2/"):
            dest = MEDIA / "F1023202" / "extracted" / rel
            n2 += 1
        else:
            dest = MEDIA / "F1023201" / "extracted" / "!LOTUS" / rel
            n1 += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(info))
    print(f"   {path.name}: {n1} files for disk 1, {n2} for disk 2")


def make_platform_image(frame, out):
    """The Pocket platform image: the game's title screen (frame 100 of the
    attract sequence), scaled whole to 521x165 grey."""
    spec = importlib.util.spec_from_file_location("artwork", ROOT / "tools" / "lotus" / "artwork.py")
    art = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(art)
    if not frame.exists():
        raise Failure(f"the title screen was not captured ({frame.name})")
    w, h, rgb = art.read_ppm(str(frame))
    out.write_bytes(art.pocket_encode(art.fit_whole(w, h, rgb, 521, 165), 521, 165))


# ---- SDK ----------------------------------------------------------------------

def fetch_sdk():
    commit = EXPECTED["sdk_commit"]
    if (SDK / "runtime").is_dir() and (SDK / "scripts" / "customize.sh").exists():
        print(f"   using {SDK.relative_to(ROOT)}")
        return
    url = f"https://codeload.github.com/openfpgaOS/openfpgaSDK/tar.gz/{commit}"
    print(f"   downloading openfpgaSDK {commit[:7]} ...", flush=True)
    SDK.parent.mkdir(parents=True, exist_ok=True)
    archive = SDK.parent / f"openfpgaSDK-{commit[:7]}.tar.gz"
    with urllib.request.urlopen(url) as r, open(archive, "wb") as out:
        shutil.copyfileobj(r, out)
    tmp = SDK.parent / "sdk-unpack"
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(archive) as t:
        try:
            t.extractall(tmp, filter="tar")
        except TypeError:                    # Python before 3.12
            t.extractall(tmp)
    shutil.rmtree(SDK, ignore_errors=True)
    (tmp / f"openfpgaSDK-{commit}").rename(SDK)
    tmp.rmdir()
    archive.unlink()


def customize_sdk():
    if (SDK / "dist" / "lotus2").is_dir() and (SDK / "src" / "lotus2").is_dir():
        return
    run(["bash", "scripts/customize.sh", "--batch", "--name", CORE_NAME, "--short", "lotus2",
         "--author", CORE_AUTHOR, "--platform", "lotus2", "--version", CORE_VERSION, "--variant", "os25"], cwd=SDK)


# ---- main ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Build the PocketLotus2 core from your own Lotus Turbo Challenge 2 files.")
    ap.add_argument("game_files", nargs="*", help="disk images, the JASPP package zip, or folders holding them "
                    "(default: the Lotus folder next to this script)")
    ap.add_argument("--out", default=str(ROOT / "PocketLotus2-SD"),
                    help="folder to write the SD card files to (default: PocketLotus2-SD)")
    ap.add_argument("--sd", help="also copy the core to this Pocket SD card (its root folder)")
    ap.add_argument("--toolchain", choices=("auto", "host", "docker"), default="auto",
                    help="RISC-V compiler: a host toolchain, the SDK's Docker container, or auto (default)")
    args = ap.parse_args()

    print("PocketLotus2 builder")
    step("Checking tools")
    cc, container = prerequisites(args.toolchain)

    step("Looking for your game files")
    sources = args.game_files or [ROOT / "Lotus"]
    disks, packages = find_game(sources)
    shutil.rmtree(MEDIA / "F1023201", ignore_errors=True)
    shutil.rmtree(MEDIA / "F1023202", ignore_errors=True)
    if len(disks) == 2:
        print("   found both disk images")
        extract_disks(disks)
    else:
        usable = [p for p, lacking in packages if not lacking]
        if not usable:
            msg = "the game files were not found. Give the two disk images (F1023201, F1023202 .jfd) or the JASPP package zip."
            for p, lacking in packages:
                msg += f"\n   {p.name} lacks {', '.join(lacking)} (use Lotus-Turbo-Challenge-2_0-1.zip or _0-2.zip)"
            if disks:
                msg += f"\n   found only disk {', '.join(disks)}"
            raise Failure(msg)
        print(f"   found the package {usable[0].name}")
        extract_package(usable[0])

    BUILD.mkdir(parents=True, exist_ok=True)
    step("Decrypting the program")
    run([sys.executable, "tools/lotus/unpack.py"])
    print("   done")

    step("Expanding the program with the PC runner")
    host = ROOT / "build" / "host" / ("lotus_host" + EXE)
    host.parent.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "port" / "core" / f for f in ("arm26.c", "machine.c", "riscos.c", "sound.c", "view.c", "save.c")]
    run([cc, "-O2", "-o", host] + sources + [ROOT / "port" / "host" / "main.c", "-lm"])
    frames = BUILD / "frames"
    frames.mkdir(exist_ok=True)
    for f in ("game_image.bin", "musmod2.bin"):
        (BUILD / f).unlink(missing_ok=True)
    run([host, "--frames", "400", "--out", frames, "--dump-mus", BUILD / "musmod2.bin"])
    if not (BUILD / "musmod2.bin").exists():
        raise Failure("the music module did not load in the PC runner")
    check_hash(BUILD / "game_image.bin", "game_image", "program image")
    make_platform_image(frames / "frame00100.ppm", BUILD / "lotus2_platform.bin")
    check_hash(BUILD / "lotus2_platform.bin", "platform_image", "platform image (title screen)")

    step("Translating the program to C")
    for f in ("coverage.bin", "coverage_mus.bin", "leaders_extra.txt"):
        shutil.copyfile(MAPS / f, BUILD / f)
    (BUILD / "leaders_seen.txt").unlink(missing_ok=True)
    run([sys.executable, "tools/lotus/recomp.py"])
    check_hash(BUILD / "gen" / "lotus_gen.c", "lotus_gen_c", "translated code")

    step("Building the asset pack")
    run([sys.executable, "tools/lotus/pack.py"])
    check_hash(BUILD / "lotus2.dat", "lotus2_dat", "asset pack")

    step("Preparing the openfpgaOS SDK")
    fetch_sdk()
    customize_sdk()

    step("Compiling the Pocket core (a few minutes)")
    run(["bash", "port/of/build.sh"],
        env={"PYTHON": sys.executable, "USE_SDK_CONTAINER": "1" if container else "0"}, quiet=False)
    package = SDK / "build" / "pocket" / "lotus2"
    elf = package / "Assets" / "lotus2" / "common" / "lotus2.elf"
    if not elf.exists():
        raise Failure("the SDK build did not produce lotus2.elf")
    if elf.stat().st_size < 1_000_000:          # the translated game is most of the program
        raise Failure("lotus2.elf is too small: the translated game code was not linked in")

    step("Writing the SD card files")
    targets = [Path(args.out).expanduser()]
    if args.sd:
        sd = Path(args.sd).expanduser()
        if not (sd / "Cores").is_dir():
            raise Failure(f"{sd} does not look like a Pocket SD card (no Cores folder)")
        targets.append(sd)
    for t in targets:
        for part in ("Assets", "Cores", "Platforms"):
            shutil.copytree(package / part, t / part, dirs_exist_ok=True)
        print(f"   {t}")

    print(f"\nDone. Copy the Assets, Cores and Platforms folders from {targets[0]} to the root of the")
    print(f"Pocket's SD card (merge them with the folders already there). The core is listed as {CORE_NAME}")
    print("under openfpgaOS. These files contain the game: keep them for your own use, do not share them.")


if __name__ == "__main__":
    try:
        main()
    except Failure as e:
        print(f"\nStopped: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
