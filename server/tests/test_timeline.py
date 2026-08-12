"""TDD tests for TimelineCapture + _LabelCache."""
import pathlib
import time
from unittest.mock import AsyncMock

import pytest

# ── TimelineCapture ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capture_count_matches_fps_duration(tmp_path):
    """1000ms × 4fps → 4 frames."""
    png = b"\x89PNG"
    screenshot = AsyncMock(return_value=png)
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=screenshot, tmp_dir=tmp_path)
    frames = await cap.capture(duration_ms=1000, fps=4)
    assert len(frames) == 4
    assert all(f.path.exists() for f in frames)
    assert all(f.path.read_bytes() == png for f in frames)


@pytest.mark.asyncio
async def test_capture_fps_above_8_raises(tmp_path):
    """fps > 8 raises ValueError."""
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=AsyncMock(), tmp_dir=tmp_path)
    with pytest.raises(ValueError, match="fps must be"):
        await cap.capture(duration_ms=1000, fps=9)


@pytest.mark.asyncio
async def test_capture_zero_duration_returns_one_frame(tmp_path):
    """duration_ms=0 yields 1 frame minimum."""
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=AsyncMock(return_value=b"x"), tmp_dir=tmp_path)
    frames = await cap.capture(duration_ms=0, fps=4)
    assert len(frames) >= 1


@pytest.mark.asyncio
async def test_capture_tracks_paths(tmp_path):
    """track fn called for each frame."""
    tracked = []
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(
        screenshot_fn=AsyncMock(return_value=b"x"),
        tmp_dir=tmp_path,
        tmp_track_fn=tracked.append,
    )
    frames = await cap.capture(duration_ms=500, fps=2)
    assert len(tracked) == 2
    assert tracked == [f.path for f in frames]


@pytest.mark.asyncio
async def test_capture_timestamps_increase(tmp_path):
    """t_ms values are non-decreasing."""
    from luna_mcp.timeline import TimelineCapture
    cap = TimelineCapture(screenshot_fn=AsyncMock(return_value=b"x"), tmp_dir=tmp_path)
    frames = await cap.capture(duration_ms=300, fps=3)
    times = [f.t_ms for f in frames]
    assert times == sorted(times)
    assert times[0] >= 0


# ── _LabelCache ───────────────────────────────────────────────────────────────

def _make_frames():
    from luna_mcp.timeline import TimelineFrame
    return [TimelineFrame(t_ms=0, path=pathlib.Path("/tmp/x.png"))]


def test_label_cache_stores_and_retrieves():
    from luna_mcp.timeline import _LabelCache
    cache = _LabelCache()
    frames = _make_frames()
    cache.set("a", frames)
    assert cache.get("a") == frames


def test_label_cache_lru_eviction():
    """5 labels inserted with max=4 → oldest is dropped."""
    from luna_mcp.timeline import _LabelCache
    cache = _LabelCache(max_labels=4)
    for ch in "abcde":
        cache.set(ch, _make_frames())
    # 'a' was oldest — must be gone
    assert cache.get("a") is None
    assert cache.get("e") is not None


def test_label_cache_ttl_expiration():
    """Expired entry returns None."""
    from luna_mcp.timeline import _LabelCache
    cache = _LabelCache(ttl_s=0.01)
    cache.set("x", _make_frames())
    time.sleep(0.05)
    assert cache.get("x") is None


def test_label_cache_clear():
    from luna_mcp.timeline import _LabelCache
    cache = _LabelCache()
    cache.set("a", _make_frames())
    cache.clear()
    assert cache.get("a") is None
