from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins" / "codex-handoff" / "hooks" / "codex_handoff_hook.py"
PLUGIN_ROOT = ROOT / "plugins" / "codex-handoff"
SKILL = PLUGIN_ROOT / "skills" / "codex-handoff" / "SKILL.md"
VERIFY_IDENTITY = SKILL.parent / "scripts" / "verify_identity.py"
WRONG_MARKER = "WRONG_HANDOFF_SKILL_USED"


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data_dir = self.base / "plugin-data"
        self.codex_home = self.base / "codex-home"

    def run_hook(
        self,
        event: str,
        *,
        session_id: str | None = "session-1",
        threshold: int | None = 3,
        stop_hook_active: bool = False,
        trigger: str | None = None,
        plugin_root: Path | None = PLUGIN_ROOT,
        profile_skill: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        payload: dict[str, object] = {
            "hook_event_name": event,
            "cwd": str(self.base / "workspace"),
            "turn_id": "turn-1",
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if stop_hook_active:
            payload["stop_hook_active"] = True
        if trigger is not None:
            payload["trigger"] = trigger

        env = os.environ.copy()
        env["PLUGIN_DATA"] = str(self.data_dir)
        env["CODEX_HOME"] = str(self.codex_home)
        if plugin_root is None:
            env.pop("PLUGIN_ROOT", None)
        else:
            env["PLUGIN_ROOT"] = str(plugin_root)
        if profile_skill is None:
            env.pop("CODEX_HANDOFF_SKILL_PATH", None)
        else:
            env["CODEX_HANDOFF_SKILL_PATH"] = str(profile_skill)
        env.pop("CODEX_HANDOFF_CONFIG", None)
        if threshold is None:
            env.pop("CODEX_HANDOFF_COMPACT_THRESHOLD", None)
        else:
            env["CODEX_HANDOFF_COMPACT_THRESHOLD"] = str(threshold)

        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )

    def state(self) -> dict[str, object]:
        return json.loads((self.data_dir / "state.json").read_text(encoding="utf-8"))

    def events(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in (self.data_dir / "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def dispatch_identity(self, reason: str) -> dict[str, str]:
        match = re.search(r"CODEX_HANDOFF_DISPATCH=(\{.*\})", reason)
        self.assertIsNotNone(match, reason)
        value = json.loads(match.group(1))
        self.assertIsInstance(value, dict)
        return value

    def make_skill(self, root: Path, name: str, body: str = "") -> Path:
        skill = root / "skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            f"---\nname: {name}\ndescription: fixture skill\n---\n\n{body}\n",
            encoding="utf-8",
        )
        scripts = skill.parent / "scripts"
        scripts.mkdir()
        shutil.copy2(VERIFY_IDENTITY, scripts / "verify_identity.py")
        return skill

    def test_postcompact_counts_completed_events_without_stdout(self) -> None:
        result = self.run_hook("PostCompact", trigger="auto")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count_since_handoff"], 1)
        self.assertEqual(entry["total_compactions"], 1)
        self.assertFalse(entry["pending_handoff"])

    def test_normal_stop_always_emits_valid_json(self) -> None:
        result = self.run_hook("Stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"continue": True})

    def test_missing_session_id_stop_emits_valid_json(self) -> None:
        result = self.run_hook("Stop", session_id=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"continue": True})

    def test_threshold_waits_for_stop_and_resets_counter(self) -> None:
        for _ in range(3):
            result = self.run_hook("PostCompact")
            self.assertEqual(result.stdout, "")

        pending = self.state()["session-1"]
        self.assertTrue(pending["pending_handoff"])
        self.assertEqual(pending["compact_count_since_handoff"], 3)

        result = self.run_hook("Stop")
        output = json.loads(result.stdout)
        self.assertEqual(output["decision"], "block")
        identity = self.dispatch_identity(output["reason"])
        self.assertEqual(identity["name"], "codex-handoff")
        self.assertEqual(identity["skill_file"], str(SKILL.resolve()))
        self.assertRegex(identity["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("safe Stop boundary", output["reason"])
        self.assertIn("Do not use Skill discovery", output["reason"])

        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count_since_handoff"], 0)
        self.assertEqual(entry["total_compactions"], 3)
        self.assertEqual(entry["handoff_requests"], 1)
        self.assertFalse(entry["pending_handoff"])

    def test_threshold_recurs_after_each_handoff(self) -> None:
        identities = []
        for expected_request in (1, 2):
            for _ in range(3):
                self.run_hook("PostCompact", threshold=3)
            output = json.loads(self.run_hook("Stop", threshold=3).stdout)
            self.assertEqual(output["decision"], "block")
            identities.append(self.dispatch_identity(output["reason"]))
            entry = self.state()["session-1"]
            self.assertEqual(entry["handoff_requests"], expected_request)
            self.assertEqual(entry["compact_count_since_handoff"], 0)

        entry = self.state()["session-1"]
        self.assertEqual(entry["total_compactions"], 6)
        self.assertEqual(identities[0], identities[1])
        self.assertEqual(identities[0]["skill_file"], str(SKILL.resolve()))

    def test_competing_handoff_skill_is_never_selected(self) -> None:
        plugin_root = self.base / "plugin"
        correct = self.make_skill(plugin_root, "codex-handoff", "correct workflow")
        wrong = self.make_skill(
            self.base / "profile", "handoff", WRONG_MARKER
        )

        self.run_hook("PostCompact", threshold=1, plugin_root=plugin_root)
        output = json.loads(
            self.run_hook("Stop", threshold=1, plugin_root=plugin_root).stdout
        )
        identity = self.dispatch_identity(output["reason"])
        self.assertEqual(identity["skill_file"], str(correct.resolve()))
        self.assertNotIn(str(wrong.resolve()), output["reason"])
        self.assertNotIn(WRONG_MARKER, output["reason"])

    def test_missing_own_skill_fails_clearly_without_fallback(self) -> None:
        plugin_root = self.base / "plugin"
        wrong = self.make_skill(
            self.base / "profile", "handoff", WRONG_MARKER
        )

        self.run_hook("PostCompact", threshold=1, plugin_root=plugin_root)
        output = json.loads(
            self.run_hook("Stop", threshold=1, plugin_root=plugin_root).stdout
        )

        self.assertEqual(output["decision"], "block")
        self.assertIn("CODEX_HANDOFF_SKILL_UNAVAILABLE", output["reason"])
        self.assertIn(
            str(
                (plugin_root / "skills" / "codex-handoff" / "SKILL.md").resolve()
            ),
            output["reason"],
        )
        self.assertIn("Do not search for or invoke another handoff", output["reason"])
        self.assertNotIn(str(wrong.resolve()), output["reason"])
        self.assertNotIn(WRONG_MARKER, output["reason"])
        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count_since_handoff"], 1)
        self.assertFalse(entry["pending_handoff"])
        self.assertEqual(entry["handoff_requests"], 0)

    def test_profile_skill_path_has_same_deterministic_identity(self) -> None:
        profile_skill = self.make_skill(
            self.base / "home" / ".agents", "codex-handoff", "profile workflow"
        )
        self.run_hook(
            "PostCompact",
            threshold=1,
            plugin_root=None,
            profile_skill=profile_skill,
        )
        output = json.loads(
            self.run_hook(
                "Stop",
                threshold=1,
                plugin_root=None,
                profile_skill=profile_skill,
            ).stdout
        )
        identity = self.dispatch_identity(output["reason"])
        self.assertEqual(identity["name"], "codex-handoff")
        self.assertEqual(identity["skill_file"], str(profile_skill.resolve()))

    def test_stop_hook_active_preserves_pending_before_normal_stop(self) -> None:
        self.run_hook("PostCompact", threshold=1)
        result = self.run_hook("Stop", threshold=1, stop_hook_active=True)
        self.assertEqual(json.loads(result.stdout), {"continue": True})
        self.assertTrue(self.state()["session-1"]["pending_handoff"])

        result = self.run_hook("Stop", threshold=1, stop_hook_active=False)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

    def test_continuation_stop_does_not_dispatch_again(self) -> None:
        self.run_hook("PostCompact", threshold=1)
        first = json.loads(self.run_hook("Stop", threshold=1).stdout)
        self.assertEqual(first["decision"], "block")

        continuation = self.run_hook(
            "Stop", threshold=1, stop_hook_active=True
        )
        self.assertEqual(json.loads(continuation.stdout), {"continue": True})
        entry = self.state()["session-1"]
        self.assertEqual(entry["handoff_requests"], 1)
        self.assertEqual(entry["compact_count_since_handoff"], 0)
        self.assertFalse(entry["pending_handoff"])
        self.assertEqual(self.events()[-1]["action"], "continuation_stop")

    def test_plugin_data_config_sets_threshold(self) -> None:
        self.data_dir.mkdir(parents=True)
        (self.data_dir / "config.json").write_text(
            '{"compact_threshold": 2}\n', encoding="utf-8"
        )
        self.run_hook("PostCompact", threshold=None)
        self.run_hook("PostCompact", threshold=None)
        output = json.loads(self.run_hook("Stop", threshold=None).stdout)
        self.assertEqual(output["decision"], "block")
        self.assertIn("threshold of 2", output["reason"])

    def test_old_and_corrupt_entries_do_not_break_hook(self) -> None:
        self.data_dir.mkdir(parents=True)
        stale = time.time() - 31 * 24 * 60 * 60
        (self.data_dir / "state.json").write_text(
            json.dumps(
                {
                    "old-session": {"updated_at": stale, "count": 99},
                    "session-1": {
                        "updated_at": "invalid",
                        "count": "invalid",
                        "handoff_requests": "invalid",
                    },
                }
            ),
            encoding="utf-8",
        )
        result = self.run_hook("PostCompact")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.state()
        self.assertNotIn("old-session", state)
        self.assertEqual(state["session-1"]["compact_count_since_handoff"], 1)

    def test_audit_log_is_local_and_records_no_prompt(self) -> None:
        self.run_hook("PostCompact")
        records = [
            json.loads(line)
            for line in (self.data_dir / "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["event"], "PostCompact")
        self.assertNotIn("prompt", records[0])
        self.assertNotIn("transcript_path", records[0])

    def test_handoff_audit_records_stable_skill_provenance(self) -> None:
        self.run_hook("PostCompact", threshold=1)
        output = json.loads(self.run_hook("Stop", threshold=1).stdout)
        identity = self.dispatch_identity(output["reason"])
        event = self.events()[-1]
        self.assertEqual(event["action"], "handoff_requested_at_safe_stop")
        self.assertEqual(event["skill_identity"], "codex-handoff")
        self.assertEqual(event["skill_path"], identity["skill_file"])
        self.assertEqual(event["skill_sha256"], identity["sha256"])
        self.assertNotIn("prompt", event)

    def test_manual_invocation_contract_remains_explicit_only(self) -> None:
        skill_text = SKILL.read_text(encoding="utf-8")
        openai_yaml = (
            SKILL.parent / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("name: codex-handoff", skill_text)
        self.assertIn("allow_implicit_invocation: false", openai_yaml)
        self.assertIn("default_prompt:", openai_yaml)


if __name__ == "__main__":
    unittest.main()
