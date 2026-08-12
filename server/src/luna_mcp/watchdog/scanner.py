"""Watchdog: async post-write scan for errors after mutations."""
import asyncio
import hashlib
import time
from typing import Awaitable, Callable, Optional

WRITE_CMDS = frozenset({"set_property", "set_transform", "eval_js", "simulate_click", "simulate_touch", "simulate_key"})


class Watchdog:
    def __init__(self, call_fn: Callable[..., Awaitable[str]], metrics,
                 get_bridge: Optional[Callable] = None):
        self._call = call_fn
        self._metrics = metrics
        self._get_bridge = get_bridge
        self._pending: dict = {}
        self._dedup: dict = {}

    def schedule(self, name: str, kw: dict) -> None:
        if name not in WRITE_CMDS:
            return
        path = kw.get("path", "*")
        prev = self._pending.get(path)
        if prev and not prev.done():
            prev.cancel()
        task = asyncio.create_task(self._scan(name, kw, path))
        self._pending[path] = task

    def _read_console_errors(self) -> str:
        """Read recent error messages from the bridge buffer (no JS call)."""
        if self._get_bridge is None:
            return ""
        bridge = self._get_bridge()
        if bridge is None:
            return ""
        msgs = bridge.get_console_messages(3, "error")
        return "\n".join(str(m) for m in msgs)

    async def _scan(self, name: str, kw: dict, path: str) -> None:
        try:
            await asyncio.sleep(2.0)
            try:
                console = self._read_console_errors()
            except Exception:
                return
            if not console or "error" not in console.lower():
                return
            key = hashlib.sha256(f"{path}:{str(console)[:80]}".encode()).hexdigest()[:16]
            now = time.time()
            if now - self._dedup.get(key, 0) < 60:
                return
            self._dedup[key] = now
            self._metrics.record_call(f"watchdog/{name}", 0, 0, error="post_write_error")
        except asyncio.CancelledError:
            pass
        finally:
            self._pending.pop(path, None)

    def cancel_all(self) -> None:
        for t in self._pending.values():
            if not t.done():
                t.cancel()
        self._pending.clear()
