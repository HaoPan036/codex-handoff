#!/usr/bin/env python3
"""Install Codex Handoff as a profile skill plus user hooks.

Plugin installation is the preferred distribution path. This installer exists for
Codex surfaces that do not currently load plugins and for local development.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

BEGIN_MARKER = "# >>> codex-handoff hooks >>>"
END_MARKER = "# <<< codex-handoff hooks <<<"
LEGACY_BEGIN_MARKER = "# >>> codex-handoff-session hooks >>>"
LEGACY_END_MARKER = "# <<< codex-handoff-session hooks <<<"
HOOK_NEEDLES = (
    "codex_handoff_hook.py",
    "compact_handoff.py",
    "compact_handoff_skill.py",
    "compact_handoff_trigger.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Codex Handoff for this user.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Completed compactions before a handoff is scheduled. Default: 3.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def remove_marked_block(text: str, begin: str, end: str) -> str:
    return re.sub(
        re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
        "",
        text,
        flags=re.S,
    )


def remove_handoff_hook_groups(text: str) -> str:
    """Remove only matching Hook groups and preserve following TOML tables."""

    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    parent_hook = re.compile(
        r"^\s*\[\[hooks\.([A-Za-z][A-Za-z0-9_]*)\]\]\s*$"
    )
    any_table = re.compile(r"^\s*\[\[?([^]\r\n]+)\]\]?\s*$")

    while index < len(lines):
        parent_match = parent_hook.match(lines[index].rstrip("\n"))
        if parent_match:
            event = parent_match.group(1)
            child_name = f"hooks.{event}.hooks"
            end = index + 1
            while end < len(lines):
                table_match = any_table.match(lines[end].rstrip("\n"))
                if table_match and table_match.group(1).strip() != child_name:
                    break
                end += 1
            chunk = "".join(lines[index:end])
            if any(needle in chunk for needle in HOOK_NEEDLES):
                index = end
                continue
            output.append(chunk)
            index = end
            continue
        output.append(lines[index])
        index += 1
    return "".join(output)


def build_config(
    original: str,
    hook_path: Path,
    skill_path: Path,
    threshold: int,
    python_executable: Path,
) -> str:
    text = remove_marked_block(original, BEGIN_MARKER, END_MARKER)
    text = remove_marked_block(text, LEGACY_BEGIN_MARKER, LEGACY_END_MARKER)
    text = remove_handoff_hook_groups(text).rstrip()

    command = (
        f"CODEX_HANDOFF_COMPACT_THRESHOLD={threshold} "
        f"CODEX_HANDOFF_SKILL_PATH={shlex.quote(str(skill_path))} "
        f"{shlex.quote(str(python_executable))} {shlex.quote(str(hook_path))}"
    )
    quoted_command = json.dumps(command)
    block = f"""

{BEGIN_MARKER}
# SessionStart isolates startup, clear, and resume generations. A compact start
# acknowledges the preceding PostCompact receipt so repeated payloads can be
# distinguished from multiple compactions inside one long turn.
[[hooks.SessionStart]]
matcher = "^(startup|resume|clear|compact)$"

[[hooks.SessionStart.hooks]]
type = "command"
command = {quoted_command}
timeout = 10
statusMessage = "Isolating Codex handoff lifecycle state"

# PostCompact records only completed compactions.
# Stop schedules the handoff after the current turn reaches a safe boundary.
[[hooks.PostCompact]]
matcher = "^(manual|auto)$"

[[hooks.PostCompact.hooks]]
type = "command"
command = {quoted_command}
timeout = 10
statusMessage = "Recording completed compaction"

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = {quoted_command}
timeout = 10
statusMessage = "Checking Codex handoff threshold"

[[hooks.SessionEnd]]

[[hooks.SessionEnd.hooks]]
type = "command"
command = {quoted_command}
timeout = 3
statusMessage = "Closing Codex handoff lifecycle state"
{END_MARKER}
"""
    candidate = text + block
    tomllib.loads(candidate)
    return candidate


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, destination)
    return destination


def safe_nonnegative_int(value: object) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def plugin_installation_active(config_text: str) -> bool:
    try:
        value = tomllib.loads(config_text) if config_text.strip() else {}
    except tomllib.TOMLDecodeError:
        return False
    plugins = value.get("plugins")
    if not isinstance(plugins, dict):
        return False
    for key in ("codex-handoff@codex-handoff", "codex-handoff"):
        entry = plugins.get(key)
        if isinstance(entry, dict) and entry.get("enabled") is True:
            return True
    return False


def migrate_legacy_state(codex_home: Path, data_dir: Path) -> bool:
    destination = data_dir / "state.json"
    if destination.exists():
        return False

    legacy_candidates = [
        codex_home / "compact_handoff_skill_state_v3.json",
        codex_home / "compact_handoff_skill_state_v2.json",
        codex_home / "compact_handoff_skill_state.json",
    ]
    source = next((path for path in legacy_candidates if path.is_file()), None)
    if source is None:
        return False

    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(value, dict):
        return False

    migrated: dict[str, Any] = {}
    for session_id, raw_entry in value.items():
        if not isinstance(raw_entry, dict):
            continue
        total = safe_nonnegative_int(raw_entry.get("count"))
        requested_at = safe_nonnegative_int(
            raw_entry.get("handoff_requested_at_count")
        )
        migrated[str(session_id)] = {
            # Legacy counts have no generation-bound receipts. Preserve them as
            # diagnostic history, but never let them authorize a continuation.
            "compact_count_since_handoff": 0,
            "total_compactions": total,
            "legacy_unverified_compact_count": max(0, total - requested_at),
            "pending_handoff": False,
            "handoff_requests": 1 if requested_at > 0 else 0,
            "cwd": str(raw_entry.get("cwd") or ""),
            "updated_at": float(raw_entry.get("updated_at", time.time()) or time.time()),
            "last_handoff_requested_at": None,
        }

    data_dir.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(migrated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    legacy_log = codex_home / "compact_handoff_skill_events.jsonl"
    new_log = data_dir / "events.jsonl"
    if legacy_log.is_file() and not new_log.exists():
        shutil.copy2(legacy_log, new_log)
    return True


def main() -> int:
    args = parse_args()
    if os.name != "posix":
        print(
            "The profile installer currently supports macOS and Linux. "
            "Use the plugin package on other systems.",
            file=sys.stderr,
        )
        return 2
    if args.threshold < 1:
        print("--threshold must be at least 1.", file=sys.stderr)
        return 2
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    plugin_root = repo_root / "plugins" / "codex-handoff"
    source_skill = plugin_root / "skills" / "codex-handoff"
    source_hook = plugin_root / "hooks" / "codex_handoff_hook.py"
    if not source_skill.is_dir() or not source_hook.is_file():
        print("Run the installer from a complete codex-handoff checkout.", file=sys.stderr)
        return 1

    home = args.home.expanduser().resolve()
    codex_home = (
        args.codex_home.expanduser().resolve()
        if args.codex_home is not None
        else Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().resolve()
    )
    skill_parent = home / ".agents" / "skills"
    skill_target = skill_parent / "codex-handoff"
    legacy_skill_target = skill_parent / "codex-handoff-session"
    hook_dir = codex_home / "hooks"
    hook_target = hook_dir / "codex_handoff_hook.py"
    config_path = codex_home / "config.toml"
    data_dir = codex_home / "codex-handoff"

    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    duplicate_plugin_risk = plugin_installation_active(original)
    try:
        candidate = build_config(
            original=original,
            hook_path=hook_target,
            skill_path=skill_target / "SKILL.md",
            threshold=args.threshold,
            python_executable=Path(sys.executable).resolve(),
        )
    except tomllib.TOMLDecodeError as exc:
        print(f"Refusing to modify invalid TOML: {exc}", file=sys.stderr)
        return 1

    skill_parent.mkdir(parents=True, exist_ok=True)
    hook_dir.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_backup = backup(config_path)
    if skill_target.exists():
        shutil.rmtree(skill_target)
    shutil.copytree(source_skill, skill_target)
    shutil.copy2(source_hook, hook_target)
    hook_target.chmod(hook_target.stat().st_mode | 0o111)
    for helper in (skill_target / "scripts").glob("*.py"):
        helper.chmod(helper.stat().st_mode | 0o111)

    config_path.write_text(candidate, encoding="utf-8")
    migrated = migrate_legacy_state(codex_home, data_dir)

    if legacy_skill_target.exists():
        shutil.rmtree(legacy_skill_target)
    for legacy_hook in (
        hook_dir / "compact_handoff_skill.py",
        hook_dir / "compact_handoff.py",
        hook_dir / "compact_handoff_trigger.py",
    ):
        try:
            legacy_hook.unlink()
        except FileNotFoundError:
            pass

    print("Codex Handoff installed.")
    print(f"Skill: {skill_target}")
    print(f"Hook: {hook_target}")
    print(f"Config: {config_path}")
    print(f"Compact threshold: {args.threshold}")
    print(f"State directory: {data_dir}")
    if duplicate_plugin_risk:
        print(
            "WARNING: the Codex Handoff Plugin is enabled while this profile Hook "
            "installation is active. Codex loads both sources, which can execute "
            "handoffs twice. Disable one installation and run scripts/doctor.py.",
            file=sys.stderr,
        )
    if config_backup is not None:
        print(f"Config backup: {config_backup}")
    if migrated:
        print("Migrated compact counts from the previous safe-handoff installation.")
    print("Restart Codex, review the hook definition, and trust it before use.")
    print("Manual invocation: $codex-handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
