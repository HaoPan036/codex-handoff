#!/usr/bin/env python3
"""Remove the Codex Handoff profile installation without deleting state by default."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import tomllib
from pathlib import Path

from install_profile import (
    BEGIN_MARKER,
    END_MARKER,
    LEGACY_BEGIN_MARKER,
    LEGACY_END_MARKER,
    remove_handoff_hook_groups,
    remove_marked_block,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Uninstall Codex Handoff.")
    parser.add_argument(
        "--purge-state",
        action="store_true",
        help="Also delete local counters, configuration, and audit logs.",
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--codex-home", type=Path, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    home = args.home.expanduser().resolve()
    codex_home = (
        args.codex_home.expanduser().resolve()
        if args.codex_home is not None
        else Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().resolve()
    )

    skill_targets = [
        home / ".agents" / "skills" / "codex-handoff",
        home / ".agents" / "skills" / "codex-handoff-session",
    ]
    hook_targets = [
        codex_home / "hooks" / "codex_handoff_hook.py",
        codex_home / "hooks" / "compact_handoff_skill.py",
        codex_home / "hooks" / "compact_handoff.py",
        codex_home / "hooks" / "compact_handoff_trigger.py",
    ]
    config_path = codex_home / "config.toml"

    if config_path.exists():
        original = config_path.read_text(encoding="utf-8")
        text = remove_marked_block(original, BEGIN_MARKER, END_MARKER)
        text = remove_marked_block(text, LEGACY_BEGIN_MARKER, LEGACY_END_MARKER)
        text = remove_handoff_hook_groups(text).rstrip() + "\n"
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            print(f"Refusing to modify invalid TOML: {exc}", file=sys.stderr)
            return 1
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = config_path.with_name(f"{config_path.name}.bak.{stamp}")
        shutil.copy2(config_path, backup)
        config_path.write_text(text, encoding="utf-8")
        print(f"Config backup: {backup}")

    for target in skill_targets:
        if target.exists():
            shutil.rmtree(target)
    for target in hook_targets:
        try:
            target.unlink()
        except FileNotFoundError:
            pass

    if args.purge_state:
        shutil.rmtree(codex_home / "codex-handoff", ignore_errors=True)
        try:
            (codex_home / "codex-handoff.json").unlink()
        except FileNotFoundError:
            pass

    print("Codex Handoff profile installation removed.")
    if not args.purge_state:
        print(f"Local state retained at: {codex_home / 'codex-handoff'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
