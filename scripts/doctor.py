#!/usr/bin/env python3
"""Report active and residual Codex Handoff installations without changing them."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

CURRENT_HOOK = "codex_handoff_hook.py"
LEGACY_HOOKS = (
    "compact_handoff.py",
    "compact_handoff_skill.py",
    "compact_handoff_trigger.py",
)
PLUGIN_KEYS = (
    "codex-handoff@codex-handoff",
    "codex-handoff",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose Codex Handoff hook sources without modifying them."
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--codex-home", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    return parser.parse_args()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def plugin_enabled(config_path: Path) -> bool:
    try:
        value = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    plugins = value.get("plugins")
    if not isinstance(plugins, dict):
        return False
    for key in PLUGIN_KEYS:
        entry = plugins.get(key)
        if isinstance(entry, dict) and entry.get("enabled") is True:
            return True
    return False


def disabled_plugin_hook_entries(config_path: Path) -> list[str]:
    try:
        value = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    hooks = value.get("hooks")
    state = hooks.get("state") if isinstance(hooks, dict) else None
    if not isinstance(state, dict):
        return []
    return sorted(
        str(key)
        for key, entry in state.items()
        if str(key).startswith("codex-handoff@codex-handoff:")
        and isinstance(entry, dict)
        and entry.get("enabled") is False
    )


def user_config_sources(codex_home: Path) -> list[Path]:
    candidates = [
        codex_home / "config.toml",
        codex_home / "hooks.json",
    ]
    return [path for path in candidates if path.is_file()]


def project_config_sources(workspace: Path, codex_home: Path) -> list[Path]:
    candidates: list[Path] = []
    for directory in (workspace, *workspace.parents):
        if directory == codex_home.parent:
            continue
        candidates.extend(
            [
                directory / ".codex" / "config.toml",
                directory / ".codex" / "hooks.json",
            ]
        )
    return [path for path in candidates if path.is_file()]


def matching_sources(paths: list[Path], needles: tuple[str, ...]) -> list[str]:
    return [
        str(path)
        for path in paths
        if any(needle in read_text(path) for needle in needles)
    ]


def build_report(home: Path, codex_home: Path, workspace: Path) -> dict[str, Any]:
    user_sources = user_config_sources(codex_home)
    project_sources = project_config_sources(workspace, codex_home)
    config_path = codex_home / "config.toml"
    plugin_cache = sorted(
        str(path)
        for path in (codex_home / "plugins" / "cache").glob(
            "codex-handoff/codex-handoff/*/hooks/hooks.json"
        )
        if path.is_file()
    )
    profile_sources = matching_sources(user_sources, (CURRENT_HOOK,))
    project_hook_sources = matching_sources(project_sources, (CURRENT_HOOK,))
    legacy_sources = matching_sources(user_sources + project_sources, LEGACY_HOOKS)
    legacy_artifacts = [
        path
        for path in (
            *(codex_home / "hooks" / name for name in LEGACY_HOOKS),
            codex_home / "compact_handoff_state.json",
            codex_home / "compact_handoff_skill_state.json",
            codex_home / "compact_handoff_skill_state_v2.json",
            codex_home / "compact_handoff_skill_state_v3.json",
            home / ".agents" / "skills" / "codex-handoff-session",
        )
        if path.exists()
    ]

    plugin_installed_enabled = plugin_enabled(config_path)
    plugin_disabled_entries = disabled_plugin_hook_entries(config_path)
    plugin_active = plugin_installed_enabled and not plugin_disabled_entries
    active_hook_sources: list[str] = []
    if plugin_active:
        active_hook_sources.append("plugin")
    if profile_sources:
        active_hook_sources.append("profile")
    if project_hook_sources:
        active_hook_sources.append("project")
    if legacy_sources:
        active_hook_sources.append("legacy")
    duplicate_risk = len(active_hook_sources) > 1

    if duplicate_risk:
        remediation = (
            "Disable either the Plugin or profile/legacy Hook set, restart Codex, "
            "then rerun this doctor. Do not delete state until it has been reviewed."
        )
    elif plugin_installed_enabled and not plugin_active:
        remediation = (
            "The Plugin is enabled but one or more Hook handlers are disabled or "
            "awaiting review. Open /hooks, review the exact commands, and trust "
            "only the intended Codex Handoff source."
        )
    elif legacy_artifacts:
        remediation = (
            "No active duplicate Hook source was found. Legacy files remain inactive; "
            "review them before optional manual cleanup."
        )
    else:
        remediation = "No duplicate Codex Handoff Hook source was detected."

    return {
        "active_hook_sources": active_hook_sources,
        "plugin_installation": {
            "active": plugin_installed_enabled,
            "hook_execution_active": plugin_active,
            "disabled_hook_entries": plugin_disabled_entries,
            "cached_hook_files": plugin_cache,
        },
        "profile_installation": {
            "active": bool(profile_sources),
            "hook_sources": profile_sources,
        },
        "project_installation": {
            "active": bool(project_hook_sources),
            "hook_sources": project_hook_sources,
        },
        "legacy_installation": {
            "active": bool(legacy_sources),
            "hook_sources": legacy_sources,
            "inactive_artifacts": [str(path) for path in legacy_artifacts],
        },
        "possible_duplicate_execution_risk": duplicate_risk,
        "remediation": remediation,
        "read_only": True,
    }


def main() -> int:
    args = parse_args()
    home = args.home.expanduser().resolve()
    codex_home = (
        args.codex_home.expanduser().resolve()
        if args.codex_home is not None
        else Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().resolve()
    )
    workspace = args.workspace.expanduser().resolve()
    report = build_report(home, codex_home, workspace)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Codex Handoff doctor (read-only)")
        sources = report["active_hook_sources"]
        print("Active Hook sources: " + (", ".join(sources) if sources else "none"))
        print(
            "Duplicate execution risk: "
            + ("YES" if report["possible_duplicate_execution_risk"] else "NO")
        )
        inactive = report["legacy_installation"]["inactive_artifacts"]
        if inactive:
            print("Inactive legacy artifacts:")
            for path in inactive:
                print(f"  - {path}")
        print("Remediation: " + report["remediation"])

    return 1 if report["possible_duplicate_execution_risk"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
