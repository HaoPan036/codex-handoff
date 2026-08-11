#!/usr/bin/env python3
"""Validate the current-state plus bounded-history Codex handoff format."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_HEADINGS = [
    "# Codex Handoff",
    "## 1. Objective and scope",
    "## 2. Verified current state",
    "## 3. Architecture and data flow",
    "## 4. Decisions, constraints, and rejected approaches",
    "## 5. Relevant files and symbols",
    "## 6. Verification",
    "## 7. Working tree",
    "## 8. Known issues, risks, and unknowns",
    "## 9. Next concrete task",
    "## 10. New-session startup checklist",
    "## 11. Handoff history",
]

PLACEHOLDER_MARKERS = [
    "<ISO-8601 local timestamp>",
    "<absolute workspace path>",
    "<Current outcome being pursued>",
    "<One bounded, executable task",
    "<why this handoff was created>",
]

MAX_HISTORY_ENTRIES = 5
MAX_HISTORY_ENTRY_WORDS = 160
MAX_HANDOFF_BYTES = 300_000


def history_entries(text: str) -> list[str]:
    marker = "## 11. Handoff history"
    if marker not in text:
        return []
    history = text.split(marker, 1)[1]
    matches = list(re.finditer(r"(?m)^###\s+.+$", history))
    entries: list[str] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(history)
        entries.append(history[start:end].strip())
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CODEX_HANDOFF.md.")
    parser.add_argument("handoff_path", help="Path to CODEX_HANDOFF.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.handoff_path).expanduser().resolve()
    if not path.is_file():
        print(f"Handoff file does not exist: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    if path.stat().st_size > MAX_HANDOFF_BYTES:
        errors.append(
            f"Handoff is too large ({path.stat().st_size} bytes); keep it under "
            f"{MAX_HANDOFF_BYTES} bytes."
        )
    if len(text.strip()) < 900:
        errors.append("Handoff is too short to contain reliable project state and history.")

    heading_positions: list[int] = []
    for heading in REQUIRED_HEADINGS:
        position = text.find(heading)
        if position < 0:
            errors.append(f"Missing required heading: {heading}")
        else:
            heading_positions.append(position)
    if len(heading_positions) == len(REQUIRED_HEADINGS) and heading_positions != sorted(
        heading_positions
    ):
        errors.append("Required sections are out of order.")

    for marker in PLACEHOLDER_MARKERS:
        if marker in text:
            errors.append(f"Unresolved template placeholder: {marker}")

    if "## 9. Next concrete task" in text:
        next_task = text.split("## 9. Next concrete task", 1)[1]
        next_task = next_task.split("## 10.", 1)[0].strip()
        if len(next_task) < 40:
            errors.append("Next concrete task is missing or too vague.")

    entries = history_entries(text)
    if "## 11. Handoff history" in text and not entries:
        errors.append("Handoff history must contain the current handoff entry.")
    if len(entries) > MAX_HISTORY_ENTRIES:
        errors.append(
            f"Handoff history has {len(entries)} entries; keep at most "
            f"{MAX_HISTORY_ENTRIES}."
        )

    required_history_fields = (
        "Reason:",
        "Branch / HEAD:",
        "Key progress since previous handoff:",
        "Next task:",
    )
    for index, entry in enumerate(entries, start=1):
        words = entry.split()
        if len(words) > MAX_HISTORY_ENTRY_WORDS:
            errors.append(
                f"Handoff history entry {index} is too long ({len(words)} words); "
                f"keep it under {MAX_HISTORY_ENTRY_WORDS} words."
            )
        for required in required_history_fields:
            if required not in entry:
                errors.append(
                    f"Handoff history entry {index} is missing `{required}`."
                )

    if errors:
        print("Handoff validation failed:")
        for error in errors:
            print(f"  * {error}")
        return 1

    print(f"Handoff validation passed: {path}")
    print(f"History entries retained: {len(entries)}/{MAX_HISTORY_ENTRIES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
