from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install_profile.py"
UNINSTALL = ROOT / "scripts" / "uninstall_profile.py"


class InstallerTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_install_upgrade_migrate_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "home"
            codex_home = base / "codex"
            home.mkdir()
            codex_home.mkdir()

            old_hook = codex_home / "hooks" / "compact_handoff_skill.py"
            old_hook.parent.mkdir()
            old_hook.write_text("# old hook\n", encoding="utf-8")
            old_skill = home / ".agents" / "skills" / "codex-handoff-session"
            old_skill.mkdir(parents=True)
            (old_skill / "SKILL.md").write_text("old\n", encoding="utf-8")

            config = codex_home / "config.toml"
            config.write_text(
                """model = "test-model"

# >>> codex-handoff-session hooks >>>
[[hooks.Stop]]
[[hooks.Stop.hooks]]
type = "command"
command = "python3 /tmp/compact_handoff_skill.py"
# <<< codex-handoff-session hooks <<<

[projects."/tmp/repo"]
trust_level = "trusted"
""",
                encoding="utf-8",
            )
            (codex_home / "compact_handoff_skill_state_v3.json").write_text(
                json.dumps(
                    {
                        "session-1": {
                            "count": 5,
                            "pending_handoff": False,
                            "handoff_requested_at_count": 3,
                            "cwd": "/workspace",
                            "updated_at": 1786434000.0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_script(
                INSTALL,
                "--threshold",
                "2",
                "--home",
                str(home),
                "--codex-home",
                str(codex_home),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Codex Handoff installed", result.stdout)
            self.assertTrue(
                (home / ".agents" / "skills" / "codex-handoff" / "SKILL.md").is_file()
            )
            self.assertFalse(old_skill.exists())
            self.assertFalse(old_hook.exists())
            self.assertTrue((codex_home / "hooks" / "codex_handoff_hook.py").is_file())

            config_text = config.read_text(encoding="utf-8")
            tomllib.loads(config_text)
            self.assertEqual(config_text.count("# >>> codex-handoff hooks >>>"), 1)
            self.assertNotIn("codex-handoff-session hooks", config_text)
            self.assertIn("CODEX_HANDOFF_COMPACT_THRESHOLD=2", config_text)
            self.assertIn('[projects."/tmp/repo"]', config_text)
            self.assertIn('trust_level = "trusted"', config_text)

            migrated = json.loads(
                (codex_home / "codex-handoff" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                migrated["session-1"]["compact_count_since_handoff"], 2
            )
            self.assertEqual(migrated["session-1"]["total_compactions"], 5)

            result = self.run_script(
                INSTALL,
                "--threshold",
                "4",
                "--home",
                str(home),
                "--codex-home",
                str(codex_home),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            config_text = config.read_text(encoding="utf-8")
            self.assertEqual(config_text.count("# >>> codex-handoff hooks >>>"), 1)
            self.assertIn("CODEX_HANDOFF_COMPACT_THRESHOLD=4", config_text)
            self.assertNotIn("CODEX_HANDOFF_COMPACT_THRESHOLD=2", config_text)

            result = self.run_script(
                UNINSTALL,
                "--home",
                str(home),
                "--codex-home",
                str(codex_home),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(
                (home / ".agents" / "skills" / "codex-handoff").exists()
            )
            self.assertFalse((codex_home / "hooks" / "codex_handoff_hook.py").exists())
            self.assertNotIn(
                "codex-handoff hooks", config.read_text(encoding="utf-8")
            )
            self.assertTrue((codex_home / "codex-handoff" / "state.json").exists())

    def test_installer_rejects_invalid_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = self.run_script(
                INSTALL,
                "--threshold",
                "0",
                "--home",
                str(base / "home"),
                "--codex-home",
                str(base / "codex"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("at least 1", result.stderr)


if __name__ == "__main__":
    unittest.main()
