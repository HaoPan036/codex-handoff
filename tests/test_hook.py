from __future__ import annotations

import json
import os
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
        turn_id: str | None = "turn-1",
        threshold: int | None = 3,
        stop_hook_active: bool = False,
        trigger: str | None = None,
        source: str | None = None,
        plugin_root: Path | None = PLUGIN_ROOT,
        profile_skill: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        payload: dict[str, object] = {
            "hook_event_name": event,
            "cwd": str(self.base / "workspace"),
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if turn_id is not None:
            payload["turn_id"] = turn_id
        if stop_hook_active:
            payload["stop_hook_active"] = True
        if trigger is not None:
            payload["trigger"] = trigger
        if source is not None:
            payload["source"] = source

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

    def record_compact(
        self,
        *,
        turn_id: str = "turn-1",
        threshold: int | None = 3,
        trigger: str = "auto",
    ) -> None:
        result = self.run_hook(
            "PostCompact",
            turn_id=turn_id,
            threshold=threshold,
            trigger=trigger,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        if result.stdout:
            self.assertEqual(set(json.loads(result.stdout)), {"continue", "systemMessage"})
        result = self.run_hook(
            "SessionStart",
            turn_id=None,
            threshold=threshold,
            source="compact",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def state(self) -> dict[str, object]:
        return json.loads((self.data_dir / "state.json").read_text(encoding="utf-8"))

    def events(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in (self.data_dir / "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def test_reminders_at_five_ten_fifteen_only(self) -> None:
        reminders = []
        for count in range(1, 17):
            result = self.run_hook("PostCompact", threshold=None, trigger="auto")
            self.assertEqual(result.returncode, 0, result.stderr)
            if result.stdout:
                output = json.loads(result.stdout)
                self.assertEqual(set(output), {"continue", "systemMessage"})
                self.assertTrue(output["continue"])
                self.assertIn(f" {count} ", output["systemMessage"])
                reminders.append(count)
            self.run_hook("SessionStart", source="compact", threshold=None)
            for _ in range(2):
                output = json.loads(self.run_hook("Stop", threshold=None).stdout)
                self.assertEqual(output, {"continue": True})
        self.assertEqual(reminders, [5, 10, 15])
        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count"], 16)
        self.assertEqual(entry["last_reminded_count"], 15)
        self.assertEqual(entry["reminder_count"], 3)
        self.assertNotIn("pending_handoff", entry)

    def test_duplicate_compact_at_threshold_is_silent(self) -> None:
        for _ in range(4):
            self.record_compact(threshold=5)
        first = self.run_hook("PostCompact", trigger="auto", threshold=5)
        self.assertIn("systemMessage", json.loads(first.stdout))
        duplicate = self.run_hook("PostCompact", trigger="auto", threshold=5)
        self.assertEqual(duplicate.stdout, "")
        self.assertEqual(self.state()["session-1"]["compact_count"], 5)

    def test_same_turn_after_boundary_counts_separately(self) -> None:
        for _ in range(4):
            self.record_compact(threshold=5)
        self.assertEqual(self.state()["session-1"]["compact_count"], 4)

    def test_resume_and_startup_preserve_count_and_reminder(self) -> None:
        for _ in range(5):
            self.record_compact(threshold=5)
        before = self.state()["session-1"]
        for source in ("resume", "startup"):
            self.run_hook("SessionEnd")
            self.assertEqual(self.run_hook("SessionStart", source=source).stdout, "")
            after = self.state()["session-1"]
            for key in ("generation_id", "compact_count", "last_reminded_count"):
                self.assertEqual(after[key], before[key])
            self.assertEqual(json.loads(self.run_hook("Stop").stdout), {"continue": True})
        for _ in range(4):
            self.record_compact(threshold=5)
        result = self.run_hook("PostCompact", trigger="manual", threshold=5)
        self.assertIn(" 10 ", json.loads(result.stdout)["systemMessage"])

    def test_resume_does_not_turn_redelivery_into_new_compaction(self) -> None:
        self.run_hook("PostCompact", trigger="auto")
        self.run_hook("SessionStart", source="resume")
        self.run_hook("PostCompact", trigger="auto")
        self.assertEqual(self.state()["session-1"]["compact_count"], 1)

    def test_clear_resets_reminder_cadence(self) -> None:
        for _ in range(5):
            self.record_compact(threshold=5)
        self.run_hook("SessionStart", source="clear")
        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count"], 0)
        self.assertEqual(entry["last_reminded_count"], 0)
        self.assertEqual(entry["total_compactions"], 5)
        for _ in range(4):
            self.record_compact(threshold=5)
        result = self.run_hook("PostCompact", trigger="auto", threshold=5)
        self.assertIn(" 5 ", json.loads(result.stdout)["systemMessage"])

    def test_sessions_are_isolated(self) -> None:
        self.run_hook("PostCompact", session_id="other", threshold=1)
        result = self.run_hook("PostCompact", threshold=5)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.state()["session-1"]["compact_count"], 1)

    def test_stop_never_dispatches_even_with_continuation_flag(self) -> None:
        for active in (False, True):
            result = self.run_hook("Stop", stop_hook_active=active)
            self.assertEqual(json.loads(result.stdout), {"continue": True})

    def test_missing_identity_cannot_block_reminder(self) -> None:
        result = self.run_hook("PostCompact", threshold=1, plugin_root=self.base / "missing")
        self.assertEqual(set(json.loads(result.stdout)), {"continue", "systemMessage"})
        self.assertFalse((self.base / "workspace" / "docs").exists())

    def test_missing_session_id_stop_returns_valid_json(self) -> None:
        result = self.run_hook("Stop", session_id=None)
        self.assertEqual(json.loads(result.stdout), {"continue": True})
        self.assertFalse(self.data_dir.exists())

    def test_unknown_event_does_not_create_state(self) -> None:
        result = self.run_hook("Unknown")
        self.assertEqual(result.stdout, "")
        self.assertFalse(self.data_dir.exists())

    def test_manual_compact_uses_same_cadence(self) -> None:
        for _ in range(4):
            self.record_compact(threshold=5, trigger="manual")
        result = self.run_hook("PostCompact", threshold=5, trigger="manual")
        self.assertIn("systemMessage", json.loads(result.stdout))

    def test_plugin_config_and_environment_precedence(self) -> None:
        self.data_dir.mkdir()
        (self.data_dir / "config.json").write_text('{"compact_threshold": 2}')
        self.record_compact(threshold=None)
        result = self.run_hook("PostCompact", threshold=None)
        self.assertIn("systemMessage", json.loads(result.stdout))
        self.run_hook("SessionStart", source="clear")
        result = self.run_hook("PostCompact", threshold=1)
        self.assertIn("systemMessage", json.loads(result.stdout))

    def test_invalid_threshold_falls_back_to_five(self) -> None:
        for _ in range(4):
            self.record_compact(threshold=0)
        result = self.run_hook("PostCompact", threshold=0)
        self.assertIn(" 5 ", json.loads(result.stdout)["systemMessage"])

    def test_old_pending_cannot_dispatch_or_count_as_new_evidence(self) -> None:
        self.data_dir.mkdir()
        (self.data_dir / "state.json").write_text(json.dumps({"session-1": {
            "count": 100, "total_compactions": 100,
            "pending_handoff": True, "handoff_continuation_active": True,
            "updated_at": time.time(),
        }}))
        self.assertEqual(json.loads(self.run_hook("Stop").stdout), {"continue": True})
        self.assertEqual(self.state()["session-1"]["compact_count"], 0)
        result = self.run_hook("PostCompact", threshold=5)
        self.assertEqual(result.stdout, "")

    def test_schema_two_receipts_migrate_without_old_dispatch(self) -> None:
        self.record_compact(threshold=5)
        state = self.state()
        state["session-1"].update(schema_version=2, pending_handoff=True,
                                  handoff_continuation_active=True, total_compactions=90)
        (self.data_dir / "state.json").write_text(json.dumps(state))
        self.run_hook("SessionStart", source="resume")
        self.assertEqual(self.state()["session-1"]["compact_count"], 1)
        for _ in range(3):
            self.record_compact(threshold=5)
        result = self.run_hook("PostCompact", threshold=5)
        self.assertIn(" 5 ", json.loads(result.stdout)["systemMessage"])

    def test_counter_continues_beyond_receipt_window(self) -> None:
        self.record_compact(threshold=5)
        state = self.state()
        state["session-1"].update(compact_count=259, last_reminded_count=255)
        (self.data_dir / "state.json").write_text(json.dumps(state))
        result = self.run_hook("PostCompact", threshold=5)
        self.assertIn(" 260 ", json.loads(result.stdout)["systemMessage"])
        self.assertEqual(self.state()["session-1"]["compact_count"], 260)

    def test_inactive_generation_ignores_delayed_compact(self) -> None:
        self.run_hook("SessionEnd")
        self.assertEqual(self.run_hook("PostCompact").stdout, "")
        self.assertEqual(self.state()["session-1"]["compact_count"], 0)

    def test_corrupt_state_is_recoverable(self) -> None:
        self.data_dir.mkdir()
        (self.data_dir / "state.json").write_text("not json")
        result = self.run_hook("PostCompact", threshold=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["session-1"]["compact_count"], 1)

    def test_audit_log_records_metadata_not_prompt_or_dispatch(self) -> None:
        self.run_hook("PostCompact", threshold=1)
        event = self.events()[-1]
        self.assertEqual(event["action"], "reminder_shown")
        self.assertEqual(event["compact_count"], 1)
        for field in ("prompt", "transcript", "reason", "skill_path", "skill_sha256"):
            self.assertNotIn(field, event)

    def test_manual_skill_remains_explicit_only(self) -> None:
        policy = (SKILL.parent / "agents" / "openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", policy)


if __name__ == "__main__":
    unittest.main()
