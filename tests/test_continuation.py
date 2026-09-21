from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from test_helpers import OPEN, assert_git_scope, valid_handoff


FAKE_SERVER = '''import json, os, sys, time
from pathlib import Path
root = Path(__file__).parent
mode = (root / "mode").read_text()
name = None
cwd = None
for line in sys.stdin:
    request = json.loads(line)
    with (root / "requests.jsonl").open("a") as out:
        out.write(json.dumps(request) + "\\n")
    method = request["method"]
    if "id" not in request:
        continue
    result = {}
    if method == "thread/start":
        cwd = request["params"]["cwd"]
        result = {"thread": {"id": "test-thread", "cwd": "/wrong" if mode == "wrong-cwd" else cwd}}
    elif method == "thread/name/set":
        name = request["params"]["name"]
    elif method == "thread/read":
        result = {"thread": {"id": "test-thread", "cwd": cwd, "name": "wrong" if mode == "wrong-title" else name}}
    elif method == "turn/start":
        if mode == "reject-turn":
            print(json.dumps({"id": request["id"], "error": {"code": -1, "message": "rejected"}}), flush=True)
            continue
        if mode == "lost-response":
            sys.exit(0)
        result = {"turn": {"id": "test-turn", "status": "inProgress"}}
    # Multiple messages in one write exercise buffering and notification routing.
    print(json.dumps({"method": "test/notification", "params": {}}) + "\\n" + json.dumps({"id": request["id"], "result": result}), flush=True)
    if method == "turn/start":
        time.sleep(0.3)
        (root / "worker-alive").write_text("yes")
        print(json.dumps({"method": "turn/completed", "params": {"threadId": "test-thread", "turn": {"id": "test-turn", "status": "completed"}}}), flush=True)
'''


class ContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worktree = self.root / "worktrees" / "1234" / "project with spaces"
        (self.worktree / "docs").mkdir(parents=True)
        (self.worktree / "docs/CODEX_HANDOFF.md").write_text(valid_handoff())
        self.binary = self.root / "codex-test"
        self.binary.write_text(f"#!{sys.executable}\n" + FAKE_SERVER)
        self.binary.chmod(0o755)

    def launch(self, mode: str = "ok") -> tuple[subprocess.CompletedProcess, dict, list]:
        (self.root / "mode").write_text(mode)
        completed = subprocess.run(
            [sys.executable, str(OPEN), str(self.worktree), "--source-thread-name",
             "任务2", "--codex-bin", str(self.binary), "--json"],
            capture_output=True, text=True, timeout=10,
        )
        receipt = json.loads(completed.stdout)
        requests = [json.loads(line) for line in (self.root / "requests.jsonl").read_text().splitlines()]
        return completed, receipt, requests

    def test_worktree_auto_submits_once_and_worker_survives_launcher(self) -> None:
        completed, receipt, requests = self.launch()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(receipt["thread_creation_verified"])
        self.assertTrue(receipt["thread_name_verified"])
        self.assertTrue(receipt["prompt_submission_verified"])
        self.assertTrue(receipt["turn_started_verified"])
        self.assertIsNone(receipt["user_action_required"])
        self.assertIn("already been set and verified", receipt["startup_prompt"])
        self.assertFalse(receipt["deep_link_dispatched"])
        starts = [r for r in requests if r["method"] == "thread/start"]
        self.assertEqual(starts[0]["params"], {"cwd": str(self.worktree.resolve())})
        turns = [r for r in requests if r["method"] == "turn/start"]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["params"]["threadId"], receipt["thread_id"])
        self.assertEqual(turns[0]["params"]["input"][0]["text"], receipt["startup_prompt"])
        assert_git_scope(self, turns[0]["params"]["input"][0]["text"])
        self.assertNotIn("model", turns[0]["params"])
        self.assertEqual(receipt["requested_thread_name"], "任务3")
        deadline = time.monotonic() + 3
        while not (self.root / "worker-alive").exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        self.assertTrue((self.root / "worker-alive").exists())

    def test_rejected_turn_retains_created_id_without_manual_fallback(self) -> None:
        completed, receipt, requests = self.launch("reject-turn")
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(receipt["thread_id"], "test-thread")
        self.assertFalse(receipt["turn_started_verified"])
        self.assertFalse(receipt["deep_link_dispatched"])
        self.assertFalse(receipt["retry_safe"])
        self.assertEqual(sum(r["method"] == "thread/start" for r in requests), 1)
        self.assertEqual(sum(r["method"] == "turn/start" for r in requests), 1)

    def test_wrong_cwd_or_title_never_sends_prompt(self) -> None:
        for mode in ("wrong-cwd", "wrong-title"):
            with self.subTest(mode=mode):
                (self.root / "requests.jsonl").write_text("")
                completed, receipt, requests = self.launch(mode)
                self.assertEqual(completed.returncode, 1)
                self.assertTrue(receipt["thread_creation_verified"])
                self.assertFalse(receipt["prompt_submission_verified"])
                self.assertNotIn("turn/start", [r["method"] for r in requests])

    def test_lost_submission_response_is_uncertain_and_not_retried(self) -> None:
        completed, receipt, requests = self.launch("lost-response")
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(receipt["retry_safe"])
        self.assertEqual(receipt["launch_stage"], "turn/start")
        self.assertFalse(receipt["prompt_submission_verified"])
        self.assertEqual(sum(r["method"] == "turn/start" for r in requests), 1)

    def test_unavailable_cli_reports_failure_instead_of_opening_composer(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(OPEN), str(self.worktree), "--source-thread-name",
             "任务", "--codex-bin", str(self.root / "absent"), "--json"],
            capture_output=True, text=True, timeout=10,
        )
        receipt = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(receipt["thread_creation_verified"])
        self.assertFalse(receipt["deep_link_dispatched"])
        self.assertTrue(receipt["retry_safe"])


if __name__ == "__main__":
    unittest.main()
