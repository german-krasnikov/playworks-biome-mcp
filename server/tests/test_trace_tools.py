"""Tests for S4.3 trace_frames tool + trace_summary."""
import asyncio
from unittest.mock import patch

import pytest


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# === trace_summary unit tests ===

def test_trace_summary_frame_deltas():
    from luna_mcp.trace_summary import summarize
    # 3 frames at 0, 16ms, 32ms → 2 deltas of 16ms each
    chunks = [
        {"name": "DrawFrame", "ts": 0},
        {"name": "DrawFrame", "ts": 16_000},
        {"name": "DrawFrame", "ts": 32_000},
    ]
    result = summarize(chunks)
    assert "avg_frame" in result
    assert "16.0ms" in result
    assert "fps" in result


def test_trace_summary_jank_count():
    from luna_mcp.trace_summary import summarize
    # Two frames: 50ms apart → jank
    chunks = [
        {"name": "DrawFrame", "ts": 0},
        {"name": "DrawFrame", "ts": 50_000},
        {"name": "DrawFrame", "ts": 100_000},
    ]
    result = summarize(chunks)
    assert "jank_frames" in result
    assert "2" in result  # both deltas >33ms


def test_trace_summary_no_frame_markers_fallback():
    from luna_mcp.trace_summary import summarize
    # No DrawFrame/BeginFrame/Commit events
    chunks = [
        {"name": "Task", "cat": "toplevel", "ts": 0, "dur": 100_000},
        {"name": "Task", "cat": "toplevel", "ts": 200_000, "dur": 50_000},
    ]
    result = summarize(chunks)
    assert "task-based estimate" in result or "frame markers absent" in result


def test_trace_summary_empty():
    from luna_mcp.trace_summary import summarize
    result = summarize([])
    assert "no trace" in result.lower()


def test_trace_summary_overflow_flag():
    from luna_mcp.trace_summary import summarize
    chunks = [{"name": "DrawFrame", "ts": 0}, {"name": "DrawFrame", "ts": 16_000}]
    result = summarize(chunks, overflow=True)
    assert "[truncated]" in result


def test_trace_summary_no_raw_keys():
    from luna_mcp.trace_summary import summarize
    chunks = [
        {"name": "DrawFrame", "ts": 0, "args": {"some": "data"}},
        {"name": "DrawFrame", "ts": 16_000, "args": {"other": "data"}},
    ]
    result = summarize(chunks)
    assert "args" not in result
    assert '"ts"' not in result


# === trace_tools integration tests ===

def make_bridge(calls, chunks=None):
    _chunks = chunks or [
        {"name": "DrawFrame", "ts": 0},
        {"name": "DrawFrame", "ts": 16_000},
    ]

    async def fake_send_cdp(method, params=None, **kw):
        calls.append((method, params or {}))
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)
        _trace_overflow = False

        def start_trace_collection(self):
            pass

        async def wait_trace_complete(self, timeout=10.0):
            pass

        def take_trace_chunks(self):
            return _chunks

    return FakeBridge()


def test_trace_tools_returns_1_entry():
    from luna_mcp.tools.trace_tools import register_trace_tools
    tools = register_trace_tools(FakeMCP(), lambda: None, exposed=set())
    assert "trace_frames" in tools


@pytest.mark.asyncio
async def test_trace_cdp_order():
    from luna_mcp.tools.trace_tools import register_trace_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_trace_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["trace_frames"]
    await fn(duration_ms=0)
    methods = [m for m, _ in calls]
    assert methods[0] == "Tracing.start"
    assert "Tracing.end" in methods
    # Tracing.start params
    p = next(p for m, p in calls if m == "Tracing.start")
    assert "disabled-by-default-devtools.timeline" in p.get("categories", "")
    assert p.get("transferMode") == "ReportEvents"


@pytest.mark.asyncio
async def test_trace_no_sleep_when_zero():
    from luna_mcp.tools.trace_tools import register_trace_tools
    sleep_calls = []
    calls = []
    bridge = make_bridge(calls)
    tools = register_trace_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["trace_frames"]
    with patch("asyncio.sleep", side_effect=lambda s: sleep_calls.append(s)):
        await fn(duration_ms=0)
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_trace_summary_from_fixture():
    from luna_mcp.tools.trace_tools import register_trace_tools
    calls = []
    bridge = make_bridge(calls, chunks=[
        {"name": "DrawFrame", "ts": 0},
        {"name": "DrawFrame", "ts": 16_000},
        {"name": "DrawFrame", "ts": 32_000},
    ])
    tools = register_trace_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["trace_frames"]
    result = await fn(duration_ms=0)
    assert "avg_frame" in result
    # No raw event keys
    assert '"ts"' not in result
    assert "args" not in result


@pytest.mark.asyncio
async def test_trace_complete_timeout_degraded():
    from luna_mcp.tools.trace_tools import register_trace_tools
    calls = []

    class TimeoutBridge:
        _trace_overflow = False

        async def send_cdp(self, method, params=None, **kw):
            calls.append(method)
            return {}

        def start_trace_collection(self):
            pass

        async def wait_trace_complete(self, timeout=10.0):
            raise asyncio.TimeoutError()

        def take_trace_chunks(self):
            return []

    tools = register_trace_tools(FakeMCP(), lambda: TimeoutBridge(), exposed=set())
    fn, _ = tools["trace_frames"]
    result = await fn(duration_ms=0)
    assert "[DEGRADED]" in result
    assert "trace did not complete" in result


@pytest.mark.asyncio
async def test_trace_degraded_no_bridge():
    from luna_mcp.tools.trace_tools import register_trace_tools
    tools = register_trace_tools(FakeMCP(), lambda: None, exposed=set())
    fn, _ = tools["trace_frames"]
    result = await fn()
    assert "[DEGRADED]" in result


@pytest.mark.asyncio
async def test_trace_active_flag_cleared_on_exception():
    """mid-flight exception → returns [DEGRADED] AND _tracing_active is False."""
    from luna_mcp.tools.trace_tools import register_trace_tools

    class ErrorBridge:
        _tracing_active = False
        _trace_overflow = False

        async def send_cdp(self, method, params=None, **kw):
            if method == "Tracing.end":
                raise RuntimeError("tracing end failed")
            return {}

        def start_trace_collection(self):
            self._tracing_active = True

        async def wait_trace_complete(self, timeout=10.0):
            pass

        def take_trace_chunks(self):
            return []

    bridge = ErrorBridge()
    tools = register_trace_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["trace_frames"]
    result = await fn(duration_ms=0)
    assert "[DEGRADED]" in result
    assert bridge._tracing_active is False
