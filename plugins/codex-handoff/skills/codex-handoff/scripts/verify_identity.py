#!/usr/bin/env python3
"""Verify the exact Codex Handoff Skill file and emit a provenance receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_NAME = "codex-handoff"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_file", type=Path)
    parser.add_argument("--expect-sha256")
    return parser.parse_args()


def parse_skill_name(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("\"'")
    return None


def fail(message: str) -> int:
    print(
        json.dumps(
            {
                "error": "CODEX_HANDOFF_SKILL_IDENTITY_ERROR",
                "message": message,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 1


def main() -> int:
    args = parse_args()
    skill_file = args.skill_file.expanduser().resolve()
    try:
        content = skill_file.read_bytes()
    except OSError as exc:
        return fail(f"cannot read {skill_file}: {exc.strerror or exc}")

    try:
        name = parse_skill_name(content.decode("utf-8"))
    except UnicodeDecodeError:
        return fail(f"{skill_file} is not valid UTF-8")
    if name != EXPECTED_NAME:
        return fail(
            f"{skill_file} declares Skill name {name!r}, expected {EXPECTED_NAME!r}"
        )

    digest = hashlib.sha256(content).hexdigest()
    if args.expect_sha256 and digest != args.expect_sha256.lower():
        return fail(
            f"{skill_file} SHA-256 is {digest}, expected "
            f"{args.expect_sha256.lower()}"
        )

    print(
        json.dumps(
            {
                "name": name,
                "sha256": digest,
                "skill_file": str(skill_file),
                "verified": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
