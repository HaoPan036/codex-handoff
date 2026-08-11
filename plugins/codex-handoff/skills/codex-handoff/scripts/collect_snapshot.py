#!/usr/bin/env python3
"""Collect bounded, deterministic repository evidence for a Codex handoff."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

COMMAND_TIMEOUT_SECONDS = 20
MAX_OUTPUT_CHARS = 40_000


def run(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

    stdout = result.stdout.rstrip()
    stderr = result.stderr.rstrip()
    if len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[:MAX_OUTPUT_CHARS] + "\n...[truncated by snapshot helper]"
    if len(stderr) > MAX_OUTPUT_CHARS:
        stderr = stderr[:MAX_OUTPUT_CHARS] + "\n...[truncated by snapshot helper]"

    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def resolve_workspace(start: Path) -> tuple[Path, bool]:
    probe = run(["git", "rev-parse", "--show-toplevel"], start)
    if probe["returncode"] == 0 and probe["stdout"]:
        return Path(probe["stdout"]).expanduser().resolve(), True
    return start.expanduser().resolve(), False


def applicable_agents_files(root: Path, cwd: Path) -> list[str]:
    root = root.resolve()
    cwd = cwd.resolve()

    try:
        relative = cwd.relative_to(root)
    except ValueError:
        candidates = [root, cwd]
    else:
        candidates = [root]
        current = root
        for part in relative.parts:
            current = current / part
            candidates.append(current)

    found: list[str] = []
    for directory in candidates:
        path = directory / "AGENTS.md"
        if path.is_file():
            found.append(str(path))
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded Git and workspace evidence for CODEX_HANDOFF.md."
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=os.getcwd(),
        help="Workspace path. Defaults to the current working directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = Path(args.workspace).expanduser()
    if not start.exists() or not start.is_dir():
        print(
            json.dumps(
                {"error": f"Workspace does not exist or is not a directory: {start}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    start = start.resolve()
    root, is_git = resolve_workspace(start)
    handoff = root / "docs" / "CODEX_HANDOFF.md"
    snapshot: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "requested_cwd": str(start),
        "workspace_root": str(root),
        "is_git_repository": is_git,
        "handoff_path": str(handoff),
        "handoff_exists": handoff.is_file(),
        "handoff_size_bytes": handoff.stat().st_size if handoff.is_file() else 0,
        "applicable_agents_files": applicable_agents_files(root, start),
    }

    if is_git:
        commands = {
            "branch": ["git", "branch", "--show-current"],
            "head": ["git", "rev-parse", "HEAD"],
            "status": ["git", "status", "--short", "--branch"],
            "recent_commits": [
                "git",
                "log",
                "-n",
                "30",
                "--date=iso-strict",
                "--pretty=format:%h%x09%ad%x09%s",
            ],
            "unstaged_name_status": ["git", "diff", "--name-status"],
            "unstaged_stat": ["git", "diff", "--stat"],
            "staged_name_status": ["git", "diff", "--cached", "--name-status"],
            "staged_stat": ["git", "diff", "--cached", "--stat"],
            "untracked": ["git", "ls-files", "--others", "--exclude-standard"],
            "diff_check": ["git", "diff", "--check"],
            "staged_diff_check": ["git", "diff", "--cached", "--check"],
        }
        snapshot["git"] = {
            name: run(command, root) for name, command in commands.items()
        }

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
