#!/usr/bin/env python3
"""Create a deterministic source archive for the current project version."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugins" / "codex-handoff" / ".codex-plugin" / "plugin.json"
DIST = ROOT / "dist"
EXCLUDED_PARTS = {".git", "dist", "__pycache__", ".pytest_cache", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
FIXED_TIMESTAMP = (2026, 8, 11, 0, 0, 0)


def included_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest["version"]
    prefix = f"codex-handoff-v{version}"
    DIST.mkdir(parents=True, exist_ok=True)
    archive = DIST / f"{prefix}.zip"
    temporary = archive.with_suffix(".zip.tmp")

    try:
        temporary.unlink()
    except FileNotFoundError:
        pass

    with zipfile.ZipFile(
        temporary,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as output:
        for path in included_files():
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=FIXED_TIMESTAMP)
            mode = path.stat().st_mode
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, path.read_bytes())

    shutil.move(temporary, archive)
    checksum = sha256(archive)
    checksum_path = DIST / "SHA256SUMS.txt"
    checksum_path.write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")

    print(f"Created: {archive}")
    print(f"SHA256: {checksum}")
    print(f"Files: {len(included_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
