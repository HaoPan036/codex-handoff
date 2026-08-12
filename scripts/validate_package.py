#!/usr/bin/env python3
"""Validate the Codex Handoff repository package without third-party tools."""

from __future__ import annotations

import json
import py_compile
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "codex-handoff"
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_PATH = ROOT / ".agents" / "plugins" / "marketplace.json"
HOOKS_PATH = PLUGIN_ROOT / "hooks" / "hooks.json"
SKILL_PATH = PLUGIN_ROOT / "skills" / "codex-handoff" / "SKILL.md"
OPENAI_YAML_PATH = (
    PLUGIN_ROOT / "skills" / "codex-handoff" / "agents" / "openai.yaml"
)
PYPROJECT_PATH = ROOT / "pyproject.toml"
FLOW_VISUAL_PATH = ROOT / "docs" / "assets" / "codex-handoff-flow.svg"
DEMO_VISUAL_PATH = ROOT / "docs" / "assets" / "codex-handoff-demo.gif"
DEMO_PATH = ROOT / "docs" / "demo.md"
SMOKE_EVIDENCE_PATH = ROOT / "docs" / "smoke-test-2026-08-11.md"
IDENTITY_SMOKE_EVIDENCE_PATH = ROOT / "docs" / "smoke-test-2026-08-12.md"
IDENTITY_HELPER_PATH = (
    PLUGIN_ROOT
    / "skills"
    / "codex-handoff"
    / "scripts"
    / "verify_identity.py"
)

REQUIRED_FILES = [
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "LICENSE",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "AGENTS.md",
    FLOW_VISUAL_PATH,
    DEMO_VISUAL_PATH,
    DEMO_PATH,
    SMOKE_EVIDENCE_PATH,
    IDENTITY_SMOKE_EVIDENCE_PATH,
    MARKETPLACE_PATH,
    MANIFEST_PATH,
    HOOKS_PATH,
    PLUGIN_ROOT / "hooks" / "codex_handoff_hook.py",
    SKILL_PATH,
    OPENAI_YAML_PATH,
    PLUGIN_ROOT
    / "skills"
    / "codex-handoff"
    / "assets"
    / "CODEX_HANDOFF.template.md",
    PLUGIN_ROOT
    / "skills"
    / "codex-handoff"
    / "scripts"
    / "collect_snapshot.py",
    PLUGIN_ROOT
    / "skills"
    / "codex-handoff"
    / "scripts"
    / "validate_handoff.py",
    PLUGIN_ROOT
    / "skills"
    / "codex-handoff"
    / "scripts"
    / "open_new_session.py",
    IDENTITY_HELPER_PATH,
    ROOT / "scripts" / "install_profile.py",
    ROOT / "scripts" / "uninstall_profile.py",
]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def relative_plugin_path(raw: str) -> Path:
    if not raw.startswith("./"):
        raise ValueError(f"Plugin path must start with './': {raw}")
    candidate = (PLUGIN_ROOT / raw[2:]).resolve()
    try:
        candidate.relative_to(PLUGIN_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Plugin path escapes the plugin root: {raw}") from exc
    return candidate


def skill_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md is missing YAML frontmatter.")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter is not closed.")
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not path.is_file():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    try:
        manifest = read_json(MANIFEST_PATH)
        marketplace = read_json(MARKETPLACE_PATH)
        hooks = read_json(HOOKS_PATH)
        pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR: package metadata could not be parsed: {exc}")
        return 1

    manifest_version = str(manifest.get("version", ""))
    project_version = str(pyproject.get("project", {}).get("version", ""))
    if manifest_version != project_version:
        errors.append(
            f"Version mismatch: manifest={manifest_version!r}, "
            f"pyproject={project_version!r}"
        )
    if manifest.get("name") != "codex-handoff":
        errors.append("Plugin manifest name must be `codex-handoff`.")
    if manifest.get("skills") != "./skills/":
        errors.append("Plugin manifest skills path must be `./skills/`.")
    if "hooks" in manifest:
        errors.append(
            "Omit the manifest hooks field and use the default hooks/hooks.json path."
        )

    for key in ("skills",):
        raw_path = manifest.get(key)
        if isinstance(raw_path, str):
            try:
                target = relative_plugin_path(raw_path)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                if not target.exists():
                    errors.append(f"Manifest path does not exist: {raw_path}")

    plugin_entries = marketplace.get("plugins")
    if not isinstance(plugin_entries, list) or len(plugin_entries) != 1:
        errors.append("Marketplace must expose exactly one plugin.")
    else:
        entry = plugin_entries[0]
        if not isinstance(entry, dict):
            errors.append("Marketplace plugin entry must be an object.")
        else:
            source = entry.get("source")
            if not isinstance(source, dict):
                errors.append("Marketplace plugin source must be an object.")
            else:
                source_path = source.get("path")
                if source_path != "./plugins/codex-handoff":
                    errors.append(
                        "Marketplace source path must be `./plugins/codex-handoff`."
                    )
            policy = entry.get("policy")
            if not isinstance(policy, dict):
                errors.append("Marketplace policy is required.")
            else:
                for key in ("installation", "authentication"):
                    if not policy.get(key):
                        errors.append(f"Marketplace policy.{key} is required.")
            if not entry.get("category"):
                errors.append("Marketplace category is required.")

    hook_map = hooks.get("hooks")
    if not isinstance(hook_map, dict):
        errors.append("hooks.json must contain a hooks object.")
    else:
        if set(hook_map) != {"PostCompact", "Stop"}:
            errors.append("hooks.json must define only PostCompact and Stop.")
        for event in ("PostCompact", "Stop"):
            groups = hook_map.get(event)
            if not isinstance(groups, list) or not groups:
                errors.append(f"{event} must contain at least one hook group.")
                continue
            for group in groups:
                if not isinstance(group, dict):
                    errors.append(f"{event} hook group must be an object.")
                    continue
                handlers = group.get("hooks")
                if not isinstance(handlers, list) or not handlers:
                    errors.append(f"{event} hook group must contain handlers.")
                    continue
                for handler in handlers:
                    command = handler.get("command") if isinstance(handler, dict) else None
                    if not isinstance(command, str):
                        errors.append(f"{event} handler command is required.")
                    elif "${PLUGIN_ROOT}" not in command:
                        errors.append(f"{event} command must use `${{PLUGIN_ROOT}}`.")

    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    try:
        frontmatter = skill_frontmatter(skill_text)
    except ValueError as exc:
        errors.append(str(exc))
    else:
        if frontmatter.get("name") != "codex-handoff":
            errors.append("SKILL.md name must be `codex-handoff`.")
        if len(frontmatter.get("description", "")) < 60:
            errors.append("SKILL.md description is too short for reliable discovery.")

    openai_yaml = OPENAI_YAML_PATH.read_text(encoding="utf-8")
    if not re.search(r"allow_implicit_invocation:\s*false", openai_yaml):
        errors.append("Skill must disable implicit invocation.")

    try:
        flow_visual = ET.parse(FLOW_VISUAL_PATH).getroot()
    except (ET.ParseError, OSError) as exc:
        errors.append(f"README flow visual is not valid XML: {exc}")
    else:
        if not flow_visual.tag.endswith("svg"):
            errors.append("README flow visual root element must be `svg`.")

    try:
        demo_header = DEMO_VISUAL_PATH.read_bytes()[:6]
    except OSError as exc:
        errors.append(f"README terminal demo could not be read: {exc}")
    else:
        if demo_header not in {b"GIF87a", b"GIF89a"}:
            errors.append("README terminal demo must be a valid GIF file.")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    readme_requirements = (
        "$codex-handoff",
        "PostCompact",
        "Stop",
        "PLUGIN_DATA",
        "bash install.sh 3",
        "HaoPan036/codex-handoff",
        "docs/assets/codex-handoff-demo.gif",
        "docs/demo.md",
        "docs/smoke-test-2026-08-11.md",
        "docs/smoke-test-2026-08-12.md",
    )
    for required in readme_requirements:
        if required not in readme:
            errors.append(f"README.md is missing required term: {required}")
    for required in readme_requirements:
        if required not in readme_zh:
            errors.append(f"README.zh-CN.md is missing required term: {required}")

    python_files = sorted(
        path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )
    for path in python_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"Python compile failed for {path.relative_to(ROOT)}: {exc}")

    if errors:
        print("Package validation failed:")
        for error in errors:
            print(f"  * {error}")
        return 1

    print("Package validation passed.")
    print(f"Version: {manifest_version}")
    print(f"Python files compiled: {len(python_files)}")
    print("Plugin events: PostCompact, Stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
