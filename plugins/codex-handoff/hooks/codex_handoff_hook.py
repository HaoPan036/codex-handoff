#!/usr/bin/env python3
"""Schedule a verified Codex handoff at a safe turn boundary.

The hook has two responsibilities only:

1. Count completed PostCompact events per Codex session.
2. At the next Stop event after the threshold, request one continuation prompt
   that explicitly invokes the bundled ``$codex-handoff`` skill.

It does not inspect transcripts, modify repositories, or make network calls.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, TextIO

DEFAULT_THRESHOLD = 3
RETENTION_SECONDS = 30 * 24 * 60 * 60
MAX_LOG_BYTES = 1_000_000
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


def normalize_entry(value: object, cwd: str) -> dict[str, Any]:
    existing = value if isinstance(value, dict) else {}
    legacy_count = nonnegative_int(existing.get("count"))
    return {
        "compact_count_since_handoff": nonnegative_int(
            existing.get("compact_count_since_handoff"), legacy_count
        ),
        "total_compactions": nonnegative_int(
            existing.get("total_compactions"), legacy_count
        ),
        "pending_handoff": bool(existing.get("pending_handoff", False)),
        "handoff_requests": nonnegative_int(existing.get("handoff_requests")),
        "cwd": str(existing.get("cwd") or cwd),
        "updated_at": timestamp_value(existing.get("updated_at"), time.time()),
        "last_handoff_requested_at": existing.get("last_handoff_requested_at"),
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


def build_handoff_reason(
    compact_count: int,
    total_compactions: int,
    threshold: int,
) -> str:
    return f"""The current turn has finished at a safe Stop boundary. This Codex session completed {compact_count} context compactions since its previous handoff, reaching the configured threshold of {threshold}. The session has completed {total_compactions} compactions in total.

Now invoke the installed skill `$codex-handoff` explicitly. Create or update `docs/CODEX_HANDOFF.md` using verified repository, Git, applicable AGENTS.md, source, configuration, generated artifact, and test evidence. Validate the handoff, then attempt to open a clean Codex session for the same workspace.

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
        entry = normalize_entry(state.get(str(session_id)), cwd)
        entry["cwd"] = cwd
        entry["updated_at"] = now

        if event == "PostCompact":
            entry["compact_count_since_handoff"] += 1
            entry["total_compactions"] += 1
            if entry["compact_count_since_handoff"] >= threshold:
                entry["pending_handoff"] = True

            append_event(
                event_log_path,
                payload,
                compact_count_since_handoff=entry["compact_count_since_handoff"],
                total_compactions=entry["total_compactions"],
                threshold=threshold,
                pending_handoff=entry["pending_handoff"],
            )

        elif event == "Stop":
            pending = bool(entry["pending_handoff"])
            already_continued = bool(payload.get("stop_hook_active", False))

            if pending and not already_continued:
                compact_count = int(entry["compact_count_since_handoff"])
                total_compactions = int(entry["total_compactions"])
                entry["pending_handoff"] = False
                entry["compact_count_since_handoff"] = 0
                entry["handoff_requests"] += 1
                entry["last_handoff_requested_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S%z"
                )
                output = {
                    "decision": "block",
                    "reason": build_handoff_reason(
                        compact_count=compact_count,
                        total_compactions=total_compactions,
                        threshold=threshold,
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
                )
            else:
                output = stop_continue_output()
                append_event(
                    event_log_path,
                    payload,
                    action=(
                        "continuation_stop"
                        if already_continued
                        else "normal_stop"
                    ),
                    compact_count_since_handoff=entry[
                        "compact_count_since_handoff"
                    ],
                    total_compactions=entry["total_compactions"],
                    threshold=threshold,
                    pending_handoff=pending,
                )

        state[str(session_id)] = entry
        save_state(state_path, state)

    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
