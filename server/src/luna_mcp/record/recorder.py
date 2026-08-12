"""JSONL append-only session recorder."""
import json
import pathlib
import threading
import time
from typing import Optional


class Recorder:
    """JSONL append-only logger. One active recording at a time."""

    def __init__(self, base_dir: pathlib.Path):
        self._base = pathlib.Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active: Optional[pathlib.Path] = None
        self._sid: Optional[str] = None

    @property
    def active(self) -> bool:
        return self._active is not None

    @property
    def session_id(self) -> Optional[str]:
        return self._sid

    def start(self, name: str) -> pathlib.Path:
        if self._active is not None:
            raise RuntimeError(f"recording already active: {self._active}")
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"invalid recording name: {name}")
        self._active = self._base / f"{name}.jsonl"
        self._sid = name
        header = {"v": 1, "sid": name, "started_at": time.time()}
        with self._active.open("w") as f:
            f.write(json.dumps(header) + "\n")
        return self._active

    def stop(self) -> Optional[pathlib.Path]:
        if self._active is None:
            return None
        path = self._active
        self._active = None
        self._sid = None
        return path

    def log(self, tool: str, args: dict, result: str, ms: int) -> None:
        from .fingerprint import hash_result
        from .redact import redact_args, redact_result
        with self._lock:
            if self._active is None:
                return
            redacted = redact_result(tool, result)
            line = {
                "ts": time.time(),
                "tool": tool,
                "args": redact_args(args),
                "summary": redacted[:200],
                "hash": hash_result(redacted),
                "ms": ms,
            }
            with self._active.open("a") as f:
                f.write(json.dumps(line) + "\n")

    def list(self) -> list:
        return sorted(self._base.glob("*.jsonl"))
