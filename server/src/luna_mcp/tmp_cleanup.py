"""Temp file tracker: auto-delete /tmp/luna_*.png on age/count/exit."""
from __future__ import annotations

import atexit
import pathlib
import threading
import time
from typing import Optional

_LOCK = threading.Lock()
_TRACKED: set[pathlib.Path] = set()
_MAX_AGE_S = 600  # 10 min
_MAX_FILES = 50


def _purge_oldest() -> None:
    """Remove oldest (by mtime) files until len <= _MAX_FILES. Call with _LOCK held."""
    if len(_TRACKED) <= _MAX_FILES:
        return
    by_mtime = sorted(_TRACKED, key=lambda p: p.stat().st_mtime if p.exists() else 0)
    to_remove = by_mtime[: len(_TRACKED) - _MAX_FILES]
    for p in to_remove:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
        _TRACKED.discard(p)


def track(path: pathlib.Path) -> None:
    """Register path for cleanup. Purges oldest if over _MAX_FILES."""
    with _LOCK:
        _TRACKED.add(path)
        if len(_TRACKED) > _MAX_FILES:
            _purge_oldest()


def cleanup_old(now: Optional[float] = None) -> None:
    """Remove tracked files older than _MAX_AGE_S seconds."""
    cutoff = (now if now is not None else time.time()) - _MAX_AGE_S
    with _LOCK:
        stale = [p for p in list(_TRACKED) if p.exists() and p.stat().st_mtime < cutoff]
        for p in stale:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
            _TRACKED.discard(p)


def cleanup_all() -> None:
    """Delete all tracked files. Called at process exit."""
    with _LOCK:
        for p in list(_TRACKED):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        _TRACKED.clear()


atexit.register(cleanup_all)
