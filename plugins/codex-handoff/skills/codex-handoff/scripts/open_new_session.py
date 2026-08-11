#!/usr/bin/env python3
"""Attempt to open a clean Codex chat with a verified handoff prompt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlencode


def build_prompt(handoff_relative: str) -> str:
    return f"""Continue this repository from a verified handoff.

Before modifying anything:
1. Read every applicable AGENTS.md file.
2. Read {handoff_relative} completely.
3. Verify the handoff against git status, the latest 30 commits, relevant source files, configuration, tests, and generated artifacts.
4. Treat repository files, Git, and test results as the source of truth. Call out and correct any conflict with the handoff.
5. Briefly state the current status, the next concrete task, the files likely to change, the validation plan, and the main risk.
6. Continue only the next concrete task recorded in section 9 of the handoff.

Do not regenerate the handoff or open another session during startup. Do not commit or push unless I explicitly request it."""


def build_url(workspace: Path, prompt: str) -> str:
    return "codex://new?" + urlencode({"path": str(workspace), "prompt": prompt})


def open_url(url: str) -> tuple[bool, str]:
    system = platform.system()
    try:
        if system == "Darwin" and Path("/usr/bin/open").is_file():
            result = subprocess.run(
                ["/usr/bin/open", url],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        elif system == "Linux" and shutil.which("xdg-open"):
            result = subprocess.run(
                ["xdg-open", url],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        elif system == "Windows" and hasattr(os, "startfile"):
            os.startfile(url)  # type: ignore[attr-defined]
            return True, "Opened through the Windows URL handler."
        else:
            return False, f"No supported URL opener was found for {system}."
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)

    if result.returncode != 0:
        return False, result.stderr.strip() or "The URL opener returned a failure."
    return True, "The Codex deep link was passed to the local URL handler."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a clean Codex chat that starts from CODEX_HANDOFF.md."
    )
    parser.add_argument("workspace_root")
    parser.add_argument(
        "handoff_relative_path",
        nargs="?",
        default="docs/CODEX_HANDOFF.md",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the startup prompt without opening a URL handler.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace_root).expanduser().resolve()
    handoff_relative = args.handoff_relative_path
    handoff = workspace / handoff_relative

    if not workspace.is_dir():
        print(f"Workspace does not exist: {workspace}")
        return 1
    if not handoff.is_file() or handoff.stat().st_size == 0:
        print(f"Verified handoff is required before opening a new chat: {handoff}")
        return 1

    prompt = build_prompt(handoff_relative)
    url = build_url(workspace, prompt)

    if args.print_only:
        opened = False
        message = "Print-only mode requested."
    else:
        opened, message = open_url(url)

    result = {
        "opened": opened,
        "workspace": str(workspace),
        "handoff": str(handoff),
        "handoff_relative_path": handoff_relative,
        "message": message,
        "startup_prompt": prompt,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(message)
        print(f"Workspace: {workspace}")
        print(f"Handoff: {handoff_relative}")
        if not opened:
            print("\nManual startup prompt:\n")
            print(prompt)

    return 0 if opened or args.print_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
