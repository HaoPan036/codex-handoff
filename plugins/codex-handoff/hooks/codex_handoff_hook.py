#!/usr/bin/env python3
"""Count completed compactions and show non-blocking handoff reminders."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, TextIO

DEFAULT_THRESHOLD = 5
RETENTION_SECONDS = 30 * 24 * 60 * 60
MAX_LOG_BYTES = 1_000_000
MAX_ACTIVE_RECEIPTS = 256
STATE_SCHEMA_VERSION = 3
STATE_FILENAME = "state.json"
LOCK_FILENAME = "state.lock"
EVENT_LOG_FILENAME = "events.jsonl"
CONFIG_FILENAME = "config.json"


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
    generation = existing.get("generation_id")
    schema = nonnegative_int(existing.get("schema_version"))
    compatible = (
        schema in {2, STATE_SCHEMA_VERSION}
        and isinstance(generation, str)
        and bool(generation)
    )
    generation_index = nonnegative_int(existing.get("generation_index"))
    if not compatible:
        generation_index += 1
        generation = generation_id(session_id, "implicit", generation_index, now)
    receipts = (
        normalize_receipts(existing.get("compact_receipts"), str(generation), threshold)
        if compatible else []
    )
    if schema == STATE_SCHEMA_VERSION and compatible:
        count = max(len(receipts), nonnegative_int(existing.get("compact_count")))
        last = min(count, nonnegative_int(existing.get("last_reminded_count")))
    else:
        # Old pending/continuation flags never trigger work after upgrading.
        # Only generation-bound receipts seed the new cadence, not legacy totals.
        count = len(receipts)
        last = count // threshold * threshold
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generation_id": generation,
        "generation_index": generation_index,
        "generation_source": str(existing.get("generation_source") or "implicit"),
        "generation_active": bool(existing.get("generation_active", True)) if compatible else True,
        "compact_sequence": nonnegative_int(existing.get("compact_sequence")) if compatible else 0,
        "compact_receipts": receipts,
        "compact_count": count,
        "last_reminded_count": last,
        "reminder_count": (
            nonnegative_int(existing.get("reminder_count"))
            if schema == STATE_SCHEMA_VERSION else 0
        ),
        "total_compactions": nonnegative_int(existing.get("total_compactions"), count),
        "legacy_unverified_compact_count": max(
            nonnegative_int(existing.get("legacy_unverified_compact_count")),
            nonnegative_int(existing.get("count")) if not compatible else 0,
        ),
        "cwd": cwd,
        "updated_at": now,
    }


def start_generation(
    entry: dict[str, Any], session_id: str, source: str, now: float
) -> None:
    entry["generation_index"] += 1
    entry.update({
        "generation_id": generation_id(session_id, source, entry["generation_index"], now),
        "generation_source": source,
        "generation_active": True,
        "compact_sequence": 0,
        "compact_receipts": [],
        "compact_count": 0,
        "last_reminded_count": 0,
        "reminder_count": 0,
    })


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


def main() -> int:
    payload = read_payload()
    event = payload.get("hook_event_name")
    output: dict[str, Any] | None = stop_continue_output() if event == "Stop" else None
    session_id = payload.get("session_id")
    if not session_id or event not in {"SessionStart", "PostCompact", "Stop", "SessionEnd"}:
        if output is not None:
            print(json.dumps(output))
        return 0

    codex_home = resolve_codex_home()
    data_dir = resolve_data_dir(codex_home)
    threshold = load_threshold(data_dir, codex_home)
    state_path = data_dir / STATE_FILENAME
    with FileLock(data_dir / LOCK_FILENAME):
        now = time.time()
        state = prune_state(load_state(state_path), now)
        session_key = str(session_id)
        entry = normalize_entry(
            state.get(session_key), str(payload.get("cwd") or os.getcwd()),
            session_key, now, threshold,
        )
        action = "normal_stop"
        if event == "SessionStart":
            source = str(payload.get("source") or "unknown")
            if source == "clear":
                start_generation(entry, session_key, source, now)
                action = "generation_cleared"
            elif source in {"startup", "resume"}:
                # Reopening this same session is not a fresh conversation.
                entry["generation_active"] = True
                action = "session_resumed"
            elif source == "compact":
                entry["compact_sequence"] += 1
                action = "compact_boundary_confirmed"
            else:
                action = "unknown_session_start_source"
        elif event == "SessionEnd":
            entry["generation_active"] = False
            action = "session_ended"
        elif event == "PostCompact":
            receipt = build_receipt(entry, payload)
            duplicate = any(
                item["receipt_id"] == receipt["receipt_id"]
                for item in entry["compact_receipts"]
            )
            if not entry["generation_active"]:
                action = "inactive_compact_ignored"
            elif duplicate:
                action = "duplicate_compact_ignored"
            else:
                entry["compact_receipts"].append(receipt)
                entry["compact_receipts"] = entry["compact_receipts"][-max(MAX_ACTIVE_RECEIPTS, threshold):]
                entry["compact_count"] += 1
                entry["total_compactions"] += 1
                action = "compact_recorded"
                count = entry["compact_count"]
                milestone = count // threshold * threshold
                if milestone > entry["last_reminded_count"]:
                    output = {
                        "continue": True,
                        "systemMessage": (
                            f"本会话已累计压缩 {count} 次。需要交接时手动调用 $codex-handoff；"
                            f"当前任务照常继续。下次提醒：{milestone + threshold} 次。"
                        ),
                    }
                    entry["last_reminded_count"] = milestone
                    entry["reminder_count"] += 1
                    action = "reminder_shown"
        state[session_key] = entry
        save_state(state_path, state)
        append_event(
            data_dir / EVENT_LOG_FILENAME, payload, action=action,
            compact_count=entry["compact_count"], threshold=threshold,
            last_reminded_count=entry["last_reminded_count"],
            reminder_count=entry["reminder_count"],
            total_compactions=entry["total_compactions"],
            generation_id=entry["generation_id"],
        )
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
