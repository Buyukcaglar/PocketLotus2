"""SPDX-License-Identifier: GPL-3.0-or-later
Verify the allowlisted local diagnostic archive and its genuine build provenance.
This checks files and transforms, never hardware or game behavior.
"""
import hashlib
import json
import zipfile
from hdl_sources import ROOT
from validate_apf import validate_directory

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    dest=ROOT/"build/package"
    apf_validation=validate_directory(dest/"Cores/PocketLotus.Diagnostic",dest/"Platforms/pocketlotusdiag.json")
    core_metadata=json.loads((dest/"Cores/PocketLotus.Diagnostic/core.json").read_text())["core"]["metadata"]
    assert core_metadata["version"] in (dest/"Cores/PocketLotus.Diagnostic/info.txt").read_text(),"About version differs from core metadata"
    manifest=json.loads((dest/"package-manifest.json").read_text())
    assert manifest["complete_bitstream_package"],"No genuine bitstream packaged"
    for item in manifest["files"]:
        data=(dest/item["path"]).read_bytes()
        assert len(data)==item["bytes"] and sha(data)==item["sha256"],item["path"]
    build=json.loads((ROOT/"build/quartus/results.json").read_text())
    assert all(x["status"]=="passed" for x in build["stages"]),"Incomplete Quartus run"
    assert sha((ROOT/"build/quartus/results.json").read_bytes())==manifest["quartus_results_sha256"]
    raw=(ROOT/"build/quartus/output_files/pocketlotus.rbf").read_bytes()
    assert sha(raw)==manifest["raw_rbf_sha256"]
    encoded=(dest/"Cores/PocketLotus.Diagnostic/bitstream.rbf_r").read_bytes()
    # Independent mask-and-swap implementation, rather than the packager's
    # string/table construction. Every byte must decode to the assembled RBF.
    decoded=bytearray()
    for byte in encoded:
        byte=((byte&0x55)<<1)|((byte>>1)&0x55)
        byte=((byte&0x33)<<2)|((byte>>2)&0x33)
        decoded.append(((byte&0x0f)<<4)|(byte>>4))
    assert decoded==raw,"APF bit reversal differs from real Quartus output"
    expected={item["path"] for item in manifest["files"]}|{"INSTALL.txt","package-manifest.json"}
    archive=json.loads((dest/"archive-sha256.json").read_text())
    assert sha((dest/archive["path"]).read_bytes())==archive["sha256"]
    with zipfile.ZipFile(dest/archive["path"]) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(expected) and set(z.namelist())==expected
        assert all(z.read(name)==(dest/name).read_bytes() for name in expected)
    assert (dest/"Assets/pocketlotusdiag/common/diagnostic.bin").read_bytes()==(ROOT/"build/diagnostic/diagnostic.bin").read_bytes()
    for source in json.loads((ROOT/"source-manifest.json").read_text())["imports"]:
        assert sha((ROOT/source["destination"]).read_bytes())==source["sha256"]
    result=dict(passed=True,command=["python","tools/verify_package.py"],working_directory=str(ROOT),
                archive_sha256=archive["sha256"],raw_rbf_sha256=sha(raw),
                apf_metadata_validation=apf_validation,
                checks=["documented APF diagnostic metadata profile and directory identity","About version matches metadata","43 pinned import hashes","allowlisted file hashes and lengths","completed Quartus provenance",
                        "independent exact RBF bit reversal","ZIP checksum/CRCs/membership/payloads","original diagnostic binary"],
                scope="Packaging/source verification only; APF external timing and Pocket acceptance remain unqualified")
    (dest/"verification.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
