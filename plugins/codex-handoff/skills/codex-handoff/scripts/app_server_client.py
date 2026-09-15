"""Small stdio client for the documented Codex App Server protocol."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path


def codex_executable(explicit: str | None = None) -> str:
    configured = explicit or os.environ.get("CODEX_HANDOFF_CODEX_BIN")
    if configured:
        candidate = shutil.which(configured)
        if candidate:
            return candidate
        raise OSError(f"Codex executable is unavailable: {configured}")
    # Desktop's bundled CLI matches its protocol; a global npm CLI may be older.
    node = os.environ.get("CODEX_MCP_NODE_PATH")
    if node and len(Path(node).parents) >= 3:
        bundled = Path(node).parents[2] / "codex"
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
    candidate = shutil.which("codex")
    if candidate:
        return candidate
    raise OSError("Codex CLI unavailable; pass --codex-bin or CODEX_HANDOFF_CODEX_BIN.")


class AppServer:
    def __init__(self, executable: str, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self.sequence = 0
        self.notifications: list[dict] = []
        self.messages: queue.Queue = queue.Queue()
        self.process = subprocess.Popen(
            [executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        except (OSError, ValueError) as exc:
            self.messages.put(exc)
        finally:
            self.messages.put(EOFError("Codex App Server closed stdout."))

    def send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout: float | None = None) -> dict:
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Codex App Server response timed out.") from exc
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, dict):
            raise ValueError("Codex App Server returned a non-object message.")
        return value

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        request_id = self.sequence
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            response = self.receive(max(0, deadline - time.monotonic()))
            if response.get("id") == request_id and "method" not in response:
                if "error" in response:
                    error = response["error"]
                    raise RuntimeError(f"{method} rejected: {error}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise ValueError(f"{method} returned no result object.")
                return result
            self.notifications.append(response)

    def initialize(self) -> None:
        self.request("initialize", {"clientInfo": {
            "name": "codex_handoff", "title": "Codex Handoff", "version": "0.2.1",
        }})
        self.send({"method": "initialized", "params": {}})

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()
