#!/usr/bin/env python3
"""Schedule a verified Codex handoff at a safe turn boundary.

The hook has two responsibilities only:

1. Count generation-bound, deduplicated PostCompact receipts.
2. At the next Stop event after the threshold, bind one continuation to the
   exact bundled ``codex-handoff`` workflow file.

It does not inspect transcripts, modify repositories, or make network calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, TextIO

DEFAULT_THRESHOLD = 5
RETENTION_SECONDS = 30 * 24 * 60 * 60
MAX_LOG_BYTES = 1_000_000
MAX_ACTIVE_RECEIPTS = 256
STATE_SCHEMA_VERSION = 2
STATE_FILENAME = "state.json"
LOCK_FILENAME = "state.lock"
EVENT_LOG_FILENAME = "events.jsonl"
CONFIG_FILENAME = "config.json"
SKILL_NAME = "codex-handoff"
SKILL_RELATIVE_PATH = Path("skills") / SKILL_NAME / "SKILL.md"
IDENTITY_HELPER_RELATIVE_PATH = Path("scripts") / "verify_identity.py"


class FileLock:
    """Small cross-platform advisory lock for the local state file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: TextIO | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+", encoding="utf-8")

        if os.name == "nt":
            import msvcrt

            self.handle.seek(0, os.SEEK_END)
            if self.handle.tell() == 0:
                self.handle.write("\0")
                self.handle.flush()
            self.handle.seek(0)
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def resolve_data_dir(codex_home: Path) -> Path:
    configured = (
        os.environ.get("PLUGIN_DATA")
        or os.environ.get("CLAUDE_PLUGIN_DATA")
        or os.environ.get("CODEX_HANDOFF_DATA_DIR")
    )
    return Path(configured).expanduser() if configured else codex_home / "codex-handoff"


def positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 1 else None


def load_threshold(data_dir: Path, codex_home: Path) -> int:
    env_value = positive_int(os.environ.get("CODEX_HANDOFF_COMPACT_THRESHOLD"))
    if env_value is not None:
        return env_value

    candidates: list[Path] = []
    explicit = os.environ.get("CODEX_HANDOFF_CONFIG")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend([data_dir / CONFIG_FILENAME, codex_home / "codex-handoff.json"])

    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict):
            configured = positive_int(value.get("compact_threshold"))
            if configured is not None:
                return configured
    return DEFAULT_THRESHOLD


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def nonnegative_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def timestamp_value(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def generation_id(
    session_id: str, source: str, generation_index: int, now: float
) -> str:
    material = f"{session_id}\0{source}\0{generation_index}\0{now:.9f}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def normalize_receipts(
    value: object, expected_generation: str, minimum_capacity: int = 0
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    capacity = max(MAX_ACTIVE_RECEIPTS, minimum_capacity)
    for raw in value[-capacity:]:
        if not isinstance(raw, dict):
            continue
        receipt_id = raw.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in seen:
            continue
        if raw.get("generation_id") != expected_generation:
            continue
        receipts.append(
            {
                "receipt_id": receipt_id,
                "generation_id": expected_generation,
                "compact_sequence": nonnegative_int(raw.get("compact_sequence")),
                "turn_id": str(raw.get("turn_id") or ""),
                "trigger": str(raw.get("trigger") or "unknown"),
                "observed_at": str(raw.get("observed_at") or "UNKNOWN"),
            }
        )
        seen.add(receipt_id)
    return receipts


def normalize_entry(
    value: object, cwd: str, session_id: str, now: float, threshold: int
) -> dict[str, Any]:
    existing = value if isinstance(value, dict) else {}
    legacy_count = nonnegative_int(existing.get("count"))
    generation_index = nonnegative_int(existing.get("generation_index"))
    existing_generation = existing.get("generation_id")
    has_current_schema = (
        nonnegative_int(existing.get("schema_version")) == STATE_SCHEMA_VERSION
        and isinstance(existing_generation, str)
        and bool(existing_generation)
    )
    if has_current_schema:
        current_generation = str(existing_generation)
        receipts = normalize_receipts(
            existing.get("compact_receipts"), current_generation, threshold
        )
        legacy_unverified_count = nonnegative_int(
            existing.get("legacy_unverified_compact_count")
        )
    else:
        generation_index += 1
        current_generation = generation_id(
            session_id, "implicit", generation_index, now
        )
        # Old counters have no generation-bound receipts and cannot authorize a
        # continuation after an upgrade.
        receipts = []
        legacy_unverified_count = max(
            nonnegative_int(existing.get("legacy_unverified_compact_count")),
            nonnegative_int(existing.get("compact_count_since_handoff")),
            legacy_count,
        )

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generation_id": current_generation,
        "generation_index": generation_index,
        "generation_source": str(
            existing.get("generation_source") if has_current_schema else "implicit"
        ),
        "generation_started_at": str(
            existing.get("generation_started_at")
            if has_current_schema
            else iso_timestamp()
        ),
        "generation_active": bool(
            existing.get("generation_active", True) if has_current_schema else True
        ),
        "compact_sequence": nonnegative_int(
            existing.get("compact_sequence") if has_current_schema else 0
        ),
        "awaiting_compact_start": bool(
            existing.get("awaiting_compact_start", False)
            if has_current_schema
            else False
        ),
        "compact_receipts": receipts,
        "compact_count_since_handoff": len(receipts),
        "legacy_unverified_compact_count": legacy_unverified_count,
        "total_compactions": nonnegative_int(
            existing.get("total_compactions"), legacy_count
        ),
        "pending_handoff": (
            bool(existing.get("pending_handoff", False))
            if has_current_schema
            else False
        ),
        "handoff_requests": nonnegative_int(existing.get("handoff_requests")),
        "cwd": str(existing.get("cwd") or cwd),
        "updated_at": timestamp_value(existing.get("updated_at"), time.time()),
        "last_handoff_requested_at": existing.get("last_handoff_requested_at"),
        "last_handoff_receipt_ids": (
            existing.get("last_handoff_receipt_ids", [])
            if isinstance(existing.get("last_handoff_receipt_ids", []), list)
            else []
        ),
    }


def start_generation(
    entry: dict[str, Any], session_id: str, source: str, now: float
) -> dict[str, Any]:
    next_index = nonnegative_int(entry.get("generation_index")) + 1
    entry.update(
        {
            "schema_version": STATE_SCHEMA_VERSION,
            "generation_id": generation_id(session_id, source, next_index, now),
            "generation_index": next_index,
            "generation_source": source,
            "generation_started_at": iso_timestamp(),
            "generation_active": True,
            "compact_sequence": 0,
            "awaiting_compact_start": False,
            "compact_receipts": [],
            "compact_count_since_handoff": 0,
            "pending_handoff": False,
        }
    )
    return entry


def build_receipt(entry: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    sequence = nonnegative_int(entry.get("compact_sequence"))
    turn_id = str(payload.get("turn_id") or "")
    trigger = str(payload.get("trigger") or "unknown")
    material = "\0".join(
        [
            str(payload.get("session_id") or ""),
            str(entry["generation_id"]),
            str(sequence),
            turn_id,
            trigger,
        ]
    )
    return {
        "receipt_id": hashlib.sha256(material.encode("utf-8")).hexdigest()[:24],
        "generation_id": entry["generation_id"],
        "compact_sequence": sequence,
        "turn_id": turn_id,
        "trigger": trigger,
        "observed_at": iso_timestamp(),
    }


def prune_state(state: dict[str, Any], now: float) -> dict[str, Any]:
    cutoff = now - RETENTION_SECONDS
    return {
        key: value
        for key, value in state.items()
        if isinstance(value, dict)
        and timestamp_value(value.get("updated_at"), 0.0) >= cutoff
    }


def append_event(path: Path, payload: dict[str, Any], **extra: Any) -> None:
    """Write a bounded local audit record without affecting Codex on failure."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            rotated = path.with_name(f"{path.name}.1")
            try:
                rotated.unlink()
            except FileNotFoundError:
                pass
            path.replace(rotated)

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session_id": payload.get("session_id"),
            "turn_id": payload.get("turn_id"),
            "event": payload.get("hook_event_name"),
            "trigger": payload.get("trigger"),
            "cwd": payload.get("cwd"),
            **extra,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def stop_continue_output() -> dict[str, bool]:
    return {"continue": True}


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


def expected_skill_file() -> tuple[Path | None, str]:
    plugin_root = os.environ.get("PLUGIN_ROOT") or os.environ.get(
        "CLAUDE_PLUGIN_ROOT"
    )
    if plugin_root:
        return (
            Path(plugin_root).expanduser().resolve() / SKILL_RELATIVE_PATH,
            "plugin_root",
        )

    profile_skill = os.environ.get("CODEX_HANDOFF_SKILL_PATH")
    if profile_skill:
        return Path(profile_skill).expanduser().resolve(), "profile_installer"

    return None, "unconfigured"


def resolve_skill_identity() -> tuple[dict[str, str] | None, str]:
    skill_file, source = expected_skill_file()
    if skill_file is None:
        return None, (
            "neither the host-provided PLUGIN_ROOT nor the profile installer's "
            "CODEX_HANDOFF_SKILL_PATH is available"
        )

    try:
        content = skill_file.read_bytes()
    except OSError as exc:
        return None, f"cannot read {skill_file}: {exc.strerror or exc}"

    try:
        skill_name = parse_skill_name(content.decode("utf-8"))
    except UnicodeDecodeError:
        return None, f"{skill_file} is not valid UTF-8"
    if skill_name != SKILL_NAME:
        return None, (
            f"{skill_file} declares Skill name {skill_name!r}, expected "
            f"{SKILL_NAME!r}"
        )

    verifier_file = skill_file.parent / IDENTITY_HELPER_RELATIVE_PATH
    if not verifier_file.is_file():
        return None, f"identity verifier is unavailable: {verifier_file}"

    return (
        {
            "name": SKILL_NAME,
            "resolver": source,
            "sha256": hashlib.sha256(content).hexdigest(),
            "skill_file": str(skill_file),
            "verifier_file": str(verifier_file),
        },
        "",
    )


def build_skill_unavailable_reason(expected: Path | None, error: str) -> str:
    expected_text = str(expected) if expected is not None else "UNRESOLVED"
    return f"""CODEX_HANDOFF_SKILL_UNAVAILABLE

The automatic handoff reached a safe Stop boundary, but the hook could not verify its own exact `codex-handoff` workflow at `{expected_text}`: {error}.

Report this automatic handoff failure clearly, then stop. Do not search for or invoke another handoff Skill, do not use an equivalent workflow, and do not create or update `docs/CODEX_HANDOFF.md` in this continuation. The compact counter has been preserved for a later retry after the installation is repaired."""


def build_handoff_reason(
    compact_count: int,
    total_compactions: int,
    threshold: int,
    identity: dict[str, str],
    source_thread_id: str,
) -> str:
    dispatch = json.dumps(
        identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    context = json.dumps(
        {"source_thread_id": source_thread_id},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    verifier_command = " ".join(
        [
            "python3",
            shlex.quote(identity["verifier_file"]),
            shlex.quote(identity["skill_file"]),
            "--expect-sha256",
            identity["sha256"],
        ]
    )
    return f"""The current turn has finished at a safe Stop boundary. This Codex session completed {compact_count} context compactions since its previous handoff, reaching the configured threshold of {threshold}. The session has completed {total_compactions} compactions in total.

CODEX_HANDOFF_DISPATCH={dispatch}
CODEX_HANDOFF_CONTEXT={context}

The automatic workflow identity is fixed by the dispatch record above. Before any handoff work:

1. Run `{verifier_command}` and require a successful receipt with the same name, absolute Skill file, and SHA-256.
2. Read the exact `skill_file` from the dispatch record.
3. Follow only that file's workflow.

Do not use Skill discovery, a `$` mention, filesystem search, or any other handoff Skill. If the verifier fails, the file cannot be read, its frontmatter name is not exactly `codex-handoff`, or its hash differs from the dispatch record, report `CODEX_HANDOFF_SKILL_IDENTITY_ERROR` and stop without substituting another workflow.

During this continuation, do not resume feature implementation and do not change application source files. Preserve all staged, unstaged, and untracked work. Do not commit, push, reset, clean, discard, stash, archive, or delete anything unless the user explicitly requested it. Mark any material claim that cannot be verified as UNKNOWN.

After reporting the handoff path and clean-session status, stop work in this old session."""


def main() -> int:
    payload = read_payload()
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    cwd = str(payload.get("cwd") or os.getcwd())

    if not session_id:
        if event == "Stop":
            print(json.dumps(stop_continue_output()))
        return 0

    codex_home = resolve_codex_home()
    data_dir = resolve_data_dir(codex_home)
    data_dir.mkdir(parents=True, exist_ok=True)
    threshold = load_threshold(data_dir, codex_home)
    state_path = data_dir / STATE_FILENAME
    lock_path = data_dir / LOCK_FILENAME
    event_log_path = data_dir / EVENT_LOG_FILENAME
    output: dict[str, Any] | None = None

    with FileLock(lock_path):
        now = time.time()
        state = prune_state(load_state(state_path), now)
        session_key = str(session_id)
        entry = normalize_entry(
            state.get(session_key), cwd, session_key, now, threshold
        )
        entry["cwd"] = cwd
        entry["updated_at"] = now

        if event == "SessionStart":
            source = str(payload.get("source") or "unknown")
            previous_generation = entry["generation_id"]
            previous_count = entry["compact_count_since_handoff"]
            previous_pending = entry["pending_handoff"]

            if source in {"startup", "clear", "resume"}:
                start_generation(entry, session_key, source, now)
                action = "generation_started"
            elif source == "compact":
                entry["generation_active"] = True
                entry["compact_sequence"] += 1
                confirmed = bool(entry["awaiting_compact_start"])
                entry["awaiting_compact_start"] = False
                action = (
                    "compact_boundary_confirmed"
                    if confirmed
                    else "compact_boundary_without_receipt"
                )
            else:
                action = "unknown_session_start_source"

            append_event(
                event_log_path,
                payload,
                action=action,
                generation_id=entry["generation_id"],
                generation_source=entry["generation_source"],
                previous_generation_id=previous_generation,
                previous_compact_count=previous_count,
                previous_pending_handoff=previous_pending,
                session_start_source=source,
                compact_count_since_handoff=entry["compact_count_since_handoff"],
                pending_handoff=entry["pending_handoff"],
            )

        elif event == "SessionEnd":
            entry["generation_active"] = False
            entry["pending_handoff"] = False
            append_event(
                event_log_path,
                payload,
                action="generation_ended",
                generation_id=entry["generation_id"],
                generation_source=entry["generation_source"],
                compact_count_since_handoff=entry["compact_count_since_handoff"],
                pending_handoff=False,
            )

        elif event == "PostCompact":
            receipt = build_receipt(entry, payload)
            existing_ids = {
                item["receipt_id"] for item in entry["compact_receipts"]
            }
            duplicate = receipt["receipt_id"] in existing_ids
            if not duplicate:
                entry["compact_receipts"].append(receipt)
                receipt_capacity = max(MAX_ACTIVE_RECEIPTS, threshold)
                if len(entry["compact_receipts"]) > receipt_capacity:
                    entry["compact_receipts"] = entry["compact_receipts"][
                        -receipt_capacity:
                    ]
                entry["compact_count_since_handoff"] = len(
                    entry["compact_receipts"]
                )
                entry["total_compactions"] += 1
                entry["awaiting_compact_start"] = True
            if entry["compact_count_since_handoff"] >= threshold:
                entry["pending_handoff"] = True

            append_event(
                event_log_path,
                payload,
                action=("duplicate_compact_ignored" if duplicate else "compact_recorded"),
                generation_id=entry["generation_id"],
                generation_source=entry["generation_source"],
                receipt_id=receipt["receipt_id"],
                duplicate=duplicate,
                compact_count_since_handoff=entry["compact_count_since_handoff"],
                total_compactions=entry["total_compactions"],
                threshold=threshold,
                pending_handoff=entry["pending_handoff"],
            )

        elif event == "Stop":
            receipts = normalize_receipts(
                entry.get("compact_receipts"),
                str(entry["generation_id"]),
                threshold,
            )
            entry["compact_receipts"] = receipts
            entry["compact_count_since_handoff"] = len(receipts)
            evidence_valid = (
                bool(entry["generation_active"])
                and len(receipts) >= threshold
            )
            stale_pending = bool(entry["pending_handoff"]) and not evidence_valid
            if stale_pending:
                entry["pending_handoff"] = False
            pending = bool(entry["pending_handoff"]) and evidence_valid
            already_continued = bool(payload.get("stop_hook_active", False))

            if pending and not already_continued:
                compact_count = int(entry["compact_count_since_handoff"])
                total_compactions = int(entry["total_compactions"])
                identity, identity_error = resolve_skill_identity()
                if identity is None:
                    expected, resolver = expected_skill_file()
                    entry["pending_handoff"] = False
                    output = {
                        "decision": "block",
                        "reason": build_skill_unavailable_reason(
                            expected, identity_error
                        ),
                    }
                    append_event(
                        event_log_path,
                        payload,
                        action="handoff_skill_unavailable",
                        compact_count_since_handoff=compact_count,
                        total_compactions=total_compactions,
                        threshold=threshold,
                        expected_skill_path=(
                            str(expected) if expected is not None else None
                        ),
                        skill_resolver=resolver,
                        error=identity_error,
                    )
                else:
                    entry["pending_handoff"] = False
                    entry["compact_count_since_handoff"] = 0
                    entry["compact_receipts"] = []
                    entry["last_handoff_receipt_ids"] = [
                        receipt["receipt_id"] for receipt in receipts
                    ]
                    entry["handoff_requests"] += 1
                    entry["last_handoff_requested_at"] = iso_timestamp()
                    output = {
                        "decision": "block",
                        "reason": build_handoff_reason(
                            compact_count=compact_count,
                            total_compactions=total_compactions,
                            threshold=threshold,
                            identity=identity,
                            source_thread_id=session_key,
                        ),
                    }
                    append_event(
                        event_log_path,
                        payload,
                        action="handoff_requested_at_safe_stop",
                        compact_count_since_handoff=compact_count,
                        total_compactions=total_compactions,
                        threshold=threshold,
                        handoff_requests=entry["handoff_requests"],
                        generation_id=entry["generation_id"],
                        generation_source=entry["generation_source"],
                        receipt_ids=entry["last_handoff_receipt_ids"],
                        skill_identity=identity["name"],
                        skill_path=identity["skill_file"],
                        skill_sha256=identity["sha256"],
                        skill_resolver=identity["resolver"],
                    )
            else:
                output = stop_continue_output()
                append_event(
                    event_log_path,
                    payload,
                    action=(
                        "continuation_stop"
                        if already_continued
                        else (
                            "stale_pending_rejected"
                            if stale_pending
                            else "normal_stop"
                        )
                    ),
                    generation_id=entry["generation_id"],
                    generation_source=entry["generation_source"],
                    compact_count_since_handoff=entry[
                        "compact_count_since_handoff"
                    ],
                    total_compactions=entry["total_compactions"],
                    threshold=threshold,
                    pending_handoff=pending,
                )

        state[session_key] = entry
        save_state(state_path, state)

    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
