"""In-memory marker map with TTL. Cleared on Page.frameNavigated."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

_DEFAULT_TTL = 300.0  # 5 minutes


@dataclass
class Rect:
    id: int
    path: str
    x: int
    y: int
    w: int
    h: int
    kind: str


class MarkerMap:
    def __init__(self, ttl: float = _DEFAULT_TTL):
        self._ttl = ttl
        self._data: dict[int, Rect] = {}
        self._ts: float = 0.0

    def set(self, rects: list[Rect]) -> None:
        self._data = {r.id: r for r in rects}
        self._ts = time.monotonic()

    def get(self, id: int) -> Optional[Rect]:
        return self._data.get(id)

    def all(self) -> list[Rect]:
        return sorted(self._data.values(), key=lambda r: r.id)

    def expired(self) -> bool:
        if self._ts == 0.0:
            return True
        return (time.monotonic() - self._ts) > self._ttl

    def clear(self) -> None:
        self._data.clear()
        self._ts = 0.0
