from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import create_release


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Release Tests")
        self.git("config", "user.email", "release@example.invalid")
        self.manifest = self.root / create_release.MANIFEST
        self.manifest.parent.mkdir(parents=True)
        self.script = self.root / "install.sh"
        self.script.write_text("#!/bin/sh\nprintf 'committed source\\n'\n")
        self.script.chmod(0o755)
        self.readme = self.root / "README.md"
        self.commit_version("0.1.0", "First release\n")
        self.first_commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=self.root, check=True,
            capture_output=True, text=True,
        ).stdout

    def commit_version(self, version: str, readme: str) -> None:
        self.manifest.write_text(json.dumps({"name": "codex-handoff", "version": version}))
        self.readme.write_text(readme)
        self.git("add", ".")
        self.git("commit", "-qm", f"Release {version}")

    def test_archive_uses_committed_content_and_ignores_working_tree(self) -> None:
        self.readme.write_text("Uncommitted edits must not ship\n")
        self.git("add", "README.md")
        self.manifest.write_text('{"version": "9.9.9"}')
        (self.root / "work").mkdir()
        (self.root / "work" / "private-notes.txt").write_text("fixture scratch data")
        (self.root / ".env").write_text("DEMO_FIXTURE=not-a-secret\n")
        archive, checksum, _, commit = create_release.create_release(self.root)
        self.assertEqual(archive.name, "codex-handoff-v0.1.0.zip")
        self.assertEqual(commit, self.first_commit)
        with zipfile.ZipFile(archive) as package:
            prefix = "codex-handoff-v0.1.0/"
            self.assertEqual(package.read(prefix + "README.md"), b"First release\n")
            self.assertEqual(
                set(package.namelist()),
                {prefix + create_release.MANIFEST, prefix + "README.md", prefix + "install.sh"},
            )
        self.assertEqual(
            (archive.parent / "SHA256SUMS.txt").read_text(),
            f"{checksum}  {archive.name}\n",
        )

    def test_explicit_ref_controls_both_version_and_source(self) -> None:
        self.git("tag", "-a", "v0.1.0", "-m", "First release")
        self.commit_version("0.2.0", "Second release\n")
        older, _, _, commit = create_release.create_release(self.root, "v0.1.0")
        self.assertEqual(commit, self.first_commit)
        self.assertEqual(older.name, "codex-handoff-v0.1.0.zip")
        with zipfile.ZipFile(older) as package:
            self.assertEqual(package.read("codex-handoff-v0.1.0/README.md"), b"First release\n")
        latest, _, _, _ = create_release.create_release(self.root)
        self.assertEqual(latest.name, "codex-handoff-v0.2.0.zip")
        with zipfile.ZipFile(latest) as package:
            self.assertEqual(package.read("codex-handoff-v0.2.0/README.md"), b"Second release\n")

    def test_same_commit_is_reproducible_despite_checkout_metadata(self) -> None:
        archive, first_checksum, _, _ = create_release.create_release(self.root)
        first_bytes = archive.read_bytes()
        self.script.chmod(0o600)
        os.utime(self.script, (1_000_000, 1_000_000))
        self.readme.write_text("Different working-tree content\n")
        archive, second_checksum, _, _ = create_release.create_release(self.root)
        self.assertEqual(first_checksum, second_checksum)
        self.assertEqual(first_bytes, archive.read_bytes())
        with zipfile.ZipFile(archive) as package:
            executable = package.getinfo("codex-handoff-v0.1.0/install.sh")
            regular = package.getinfo("codex-handoff-v0.1.0/README.md")
            self.assertEqual(executable.external_attr >> 16, 0o100755)
            self.assertEqual(regular.external_attr >> 16, 0o100644)

    def test_unknown_ref_creates_no_release(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            create_release.create_release(self.root, "missing-release")
        self.assertFalse((self.root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
