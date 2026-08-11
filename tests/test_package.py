from __future__ import annotations

import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
