#!/usr/bin/env python3
"""Create a deterministic source archive from a committed Git revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "plugins/codex-handoff/.codex-plugin/plugin.json"
FIXED_TIMESTAMP = (2026, 8, 11, 0, 0, 0)


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def included_files(root: Path, commit: str) -> list[tuple[str, int, str]]:
    files: list[tuple[str, int, str]] = []
    tree = git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        raw_mode, kind, object_id = metadata.split()
        path = raw_path.decode("utf-8")
        mode = int(raw_mode, 8)
        if kind != b"blob" or mode not in {0o100644, 0o100755, 0o120000}:
            raise ValueError(f"Unsupported Git entry in release: {path}")
        files.append((path, mode, object_id.decode("ascii")))
    return sorted(files)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_release(root: Path, ref: str = "HEAD") -> tuple[Path, str, int, str]:
    commit = git(
        root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
    ).decode("ascii").strip()
    manifest = json.loads(git(root, "show", f"{commit}:{MANIFEST}"))
    version = manifest.get("version") if isinstance(manifest, dict) else None
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", version
    ):
        raise ValueError("The committed plugin manifest must contain a valid version.")
    files = included_files(root, commit)
    prefix = f"codex-handoff-v{version}"
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / f"{prefix}.zip"
    temporary = archive.with_suffix(".zip.tmp")

    try:
        temporary.unlink()
    except FileNotFoundError:
        pass

    try:
        with zipfile.ZipFile(temporary, mode="w") as output:
            for relative, mode, object_id in files:
                info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=FIXED_TIMESTAMP)
                info.create_system = 3
                info.external_attr = (0o120777 if mode == 0o120000 else mode) << 16
                output.writestr(
                    info, git(root, "cat-file", "blob", object_id),
                    compress_type=zipfile.ZIP_DEFLATED, compresslevel=9,
                )
        shutil.move(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    checksum = sha256(archive)
    checksum_path = dist / "SHA256SUMS.txt"
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    return archive, checksum, len(files), commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref", default="HEAD",
        help="Committed Git revision to package (default: HEAD; working-tree edits are excluded).",
    )
    arguments = parser.parse_args()
    try:
        archive, checksum, count, commit = create_release(ROOT, arguments.ref)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: {exc.stderr.decode('utf-8', errors='replace').strip()}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Source: {arguments.ref} ({commit})")
    print(f"Created: {archive}")
    print(f"SHA256: {checksum}")
    print(f"Files: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
