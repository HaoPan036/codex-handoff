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
        self.assertIn("$codex-handoff", output["reason"])
        self.assertIn("safe Stop boundary", output["reason"])

        entry = self.state()["session-1"]
        self.assertEqual(entry["compact_count_since_handoff"], 0)
        self.assertEqual(entry["total_compactions"], 3)
        self.assertEqual(entry["handoff_requests"], 1)
        self.assertFalse(entry["pending_handoff"])

    def test_threshold_recurs_after_each_handoff(self) -> None:
        for expected_request in (1, 2):
            for _ in range(2):
                self.run_hook("PostCompact", threshold=2)
            output = json.loads(self.run_hook("Stop", threshold=2).stdout)
            self.assertEqual(output["decision"], "block")
            entry = self.state()["session-1"]
            self.assertEqual(entry["handoff_requests"], expected_request)
            self.assertEqual(entry["compact_count_since_handoff"], 0)

        entry = self.state()["session-1"]
        self.assertEqual(entry["total_compactions"], 4)

    def test_stop_hook_active_prevents_continuation_loop(self) -> None:
        self.run_hook("PostCompact", threshold=1)
        result = self.run_hook("Stop", threshold=1, stop_hook_active=True)
        self.assertEqual(json.loads(result.stdout), {"continue": True})
        self.assertTrue(self.state()["session-1"]["pending_handoff"])

        result = self.run_hook("Stop", threshold=1, stop_hook_active=False)
        self.assertEqual(json.loads(result.stdout)["decision"], "block")

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


if __name__ == "__main__":
    unittest.main()
