from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE_PACKAGE = ROOT / "scripts" / "validate_package.py"


class PackageTests(unittest.TestCase):
    def test_package_validator(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATE_PACKAGE)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Package validation passed", result.stdout)

    def test_release_docs_must_match_manifest_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "repo"
            shutil.copytree(
                ROOT, copy,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "dist"),
            )
            manifest = json.loads(
                (copy / "plugins/codex-handoff/.codex-plugin/plugin.json").read_text()
            )
            version = manifest["version"]
            readme = copy / "README.zh-CN.md"
            readme.write_text(
                readme.read_text().replace(f"releases/tag/v{version}", "releases/tag/v0.0.0")
            )
            changelog = copy / "CHANGELOG.md"
            changelog.write_text(changelog.read_text().replace(f"## {version},", "## 0.0.0,"))
            result = subprocess.run(
                [sys.executable, str(copy / "scripts/validate_package.py")],
                cwd=copy, capture_output=True, text=True, timeout=20, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("README.zh-CN.md is missing required term", result.stdout)
            self.assertIn("CHANGELOG.md has no dated entry", result.stdout)


if __name__ == "__main__":
    unittest.main()
