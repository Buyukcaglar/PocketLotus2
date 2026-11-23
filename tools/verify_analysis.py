"""Check analysis evidence and originals without executing game or build tools.

Run from any directory with Python 3:
    python tools/verify_analysis.py
This writes only analysis/reference-lock.json and analysis/verification.json.
It never writes into Lotus/ or the reference working trees.
"""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, encoding="utf-8"
    ).strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    errors = []
    media = json.loads((ANALYSIS / "media" / "inventory.json").read_text("utf-8"))
    media_checks = []
    for item in media:
        original = Path(item["original_path"])
        check = {
            "path": str(original),
            "size_matches": original.stat().st_size == item["original_bytes"],
            "sha256_matches": digest(original) == item["original_sha256"],
        }
        media_checks.append(check)
        if not check["size_matches"] or not check["sha256_matches"]:
            errors.append("Original media changed: " + str(original))

    zip_checks = []
    comparison_path = ANALYSIS / "zip" / "comparison.json"
    if comparison_path.exists():
        comparison = json.loads(comparison_path.read_text("utf-8"))
        for item in comparison["archives"]:
            original = Path(item["archive_path"])
            check = {
                "path": str(original),
                "size_matches": original.stat().st_size == item["archive_bytes"],
                "sha256_matches": digest(original) == item["archive_sha256"],
            }
            zip_checks.append(check)
            if not check["size_matches"] or not check["sha256_matches"]:
                errors.append("Original ZIP changed: " + str(original))

    lock = []
    for repo in sorted((ROOT / "references").iterdir()):
        if not repo.is_dir() or not (repo / ".git").exists():
            continue
        origin = git(repo, "remote", "get-url", "origin")
        unused_no_checkout = (
            repo.name == "Archimedes_MiST"
            and origin.rstrip("/").removesuffix(".git") == "https://github.com/mist-devel/mist-board"
        )
        entry = {
            "directory": repo.name,
            "origin": origin,
            "commit": git(repo, "rev-parse", "HEAD"),
            "commit_date": git(repo, "show", "-s", "--format=%cI", "HEAD"),
            "working_tree_clean": None if unused_no_checkout else not bool(git(repo, "status", "--porcelain")),
            "checkout_state": "unused intentional no-checkout clone" if unused_no_checkout else "materialized source checkout",
            "shallow": git(repo, "rev-parse", "--is-shallow-repository") == "true",
        }
        if entry["working_tree_clean"] is False:
            errors.append("Reference working tree has changes: " + repo.name)
        lock.append(entry)

    loaded_json = []
    for path in sorted(ANALYSIS.rglob("*.json")):
        # Derived media metadata is checked for syntax, not exposed in output.
        if path.name in {"reference-lock.json", "verification.json"}:
            continue
        json.loads(path.read_text("utf-8"))
        loaded_json.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    main_evidence = json.loads((ANALYSIS / "pocketriscv.json").read_text("utf-8"))
    prv = next(entry for entry in lock if entry["directory"] == "PocketRiscV")
    if prv["commit"] != main_evidence["commit"]:
        errors.append("PocketRiscV evidence commit differs from checkout")

    refs = json.loads((ANALYSIS / "references" / "findings.json").read_text("utf-8"))
    for reference in refs["repositories"]:
        actual = next(entry for entry in lock if entry["directory"] == reference["name"])
        if actual["commit"] != reference["commit"]:
            errors.append("Reference evidence commit differs: " + reference["name"])

    verification = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "media": media_checks,
        "zip_archives": zip_checks,
        "reference_count": len(lock),
        "all_materialized_reference_working_trees_clean": all(entry["working_tree_clean"] is not False for entry in lock),
        "json_documents_parsed": loaded_json,
        "errors": errors,
        "passed": not errors,
        "scope": "Evidence syntax, checkout pins and original byte preservation only. No compilation, HDL simulation, synthesis, timing closure, emulator launch, game runtime, audio/video or user acceptance validation.",
    }
    (ANALYSIS / "reference-lock.json").write_text(json.dumps(lock, indent=2) + "\n", "utf-8")
    (ANALYSIS / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", "utf-8")
    print(json.dumps({
        "passed": verification["passed"],
        "originals_unchanged": all(x["sha256_matches"] and x["size_matches"] for x in media_checks + zip_checks),
        "zip_archives_checked": len(zip_checks),
        "clean_materialized_reference_checkouts": verification["all_materialized_reference_working_trees_clean"],
        "json_count": len(loaded_json),
        "reference_count": len(lock),
        "errors": errors,
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
