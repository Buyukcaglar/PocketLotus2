"""SPDX-License-Identifier: GPL-3.0-or-later
Install the pinned Windows OSS CAD Suite into ignored build/deps only.
The large archive is hash verified before extraction; existing installs are
preserved. No system PATH, package manager or user configuration is changed.
"""
import hashlib
from pathlib import Path
import subprocess
import urllib.request
from hdl_sources import ROOT

URL="https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-10-08/oss-cad-suite-windows-x64-20261008.tgz"
SHA256="86dea50f6de7dc193d6760e01f3e4317021b68097271c3555b613c16caaafb0a"

def main():
    deps=ROOT/"build/deps"
    archive=deps/"downloads/oss-cad-suite.tgz"
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        print(f"Downloading pinned 601728860-byte archive: {URL}",flush=True)
        urllib.request.urlretrieve(URL,archive)
    digest=hashlib.file_digest(archive.open("rb"),"sha256").hexdigest()
    if digest!=SHA256:
        raise SystemExit(f"Archive SHA256 mismatch: {digest}; preserved for inspection")
    suite=deps/"oss-cad-suite"
    if suite.exists():
        if not (suite/"bin/iverilog.exe").exists():
            raise SystemExit("Existing incomplete suite preserved; choose a fresh install directory")
        print("Verified archive; existing isolated suite preserved")
    else:
        subprocess.run(["tar","-xzf",str(archive),"-C",str(deps)],check=True)
        print(f"Installed {suite}")

if __name__=="__main__":main()
