"""TimelineCapture: sample N screenshots over a duration. _LabelCache: LRU TTL store."""
import asyncio
import pathlib
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class TimelineFrame:
    t_ms: int
    path: pathlib.Path


class TimelineCapture:
    """Sample N screenshots over a duration via fixed-interval polling."""

    def __init__(
        self,
        screenshot_fn: Callable[[], Awaitable[bytes]],
        tmp_dir: pathlib.Path = None,
        tmp_track_fn: Optional[Callable[[pathlib.Path], None]] = None,
    ):
        self._screenshot = screenshot_fn
        self._tmp_dir = tmp_dir or pathlib.Path("/tmp")
        self._track = tmp_track_fn or (lambda p: None)

    async def capture(self, duration_ms: int = 1000, fps: int = 4) -> list[TimelineFrame]:
        if fps < 1 or fps > 8:
            raise ValueError(f"fps must be in [1, 8]; got {fps}")
        n_frames = fps if duration_ms > 0 else 1
        interval_s = (duration_ms / 1000) / n_frames if n_frames > 0 else 0

        session_id = uuid.uuid4().hex[:8]
        frames: list[TimelineFrame] = []
        start = time.time()
        for i in range(n_frames):
            target_t = i * interval_s
            elapsed = time.time() - start
            if target_t > elapsed:
                await asyncio.sleep(target_t - elapsed)
            png = await self._screenshot()
            t_ms = int((time.time() - start) * 1000)
            path = self._tmp_dir / f"luna_tl_{session_id}_t{t_ms}.png"
            path.write_bytes(png)
            self._track(path)
            frames.append(TimelineFrame(t_ms=t_ms, path=path))
        return frames


class _LabelCache:
    """Server-side LRU+TTL cache: label → (frames, timestamp)."""

    def __init__(self, max_labels: int = 4, ttl_s: float = 60.0):
        self._cache: dict[str, tuple[list[TimelineFrame], float]] = {}
        self._max = max_labels
        self._ttl = ttl_s

    def set(self, label: str, frames: list[TimelineFrame]) -> None:
        if len(self._cache) >= self._max and label not in self._cache:
            oldest = min(self._cache.items(), key=lambda kv: kv[1][1])[0]
            self._cache.pop(oldest, None)
        self._cache[label] = (frames, time.time())

    def get(self, label: str) -> Optional[list[TimelineFrame]]:
        item = self._cache.get(label)
        if not item:
            return None
        frames, ts = item
        if time.time() - ts > self._ttl:
            self._cache.pop(label, None)
            return None
        self._cache[label] = (frames, time.time())  # update access time (LRU)
        return frames

    def clear(self) -> None:
        self._cache.clear()
