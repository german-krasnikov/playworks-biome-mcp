"""Tests for Watchdog post-write scanner."""
import asyncio

import pytest

from luna_mcp.watchdog.scanner import WRITE_CMDS, Watchdog


@pytest.fixture
def mock_metrics():
    calls = []
    class FakeMetrics:
        def record_call(self, name, cost, latency, error=None):
            calls.append((name, error))
    m = FakeMetrics()
    m.calls = calls
    return m


@pytest.fixture
def mock_call_fn():
    async def fn(cmd, **kw):
        return "console clean"
    return fn


@pytest.fixture
def error_call_fn():
    async def fn(cmd, **kw):
        return "Error: something went wrong"
    return fn


def test_schedule_only_for_write_cmds(mock_call_fn, mock_metrics):
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("get_hierarchy", {})  # not a write cmd
    assert len(wd._pending) == 0


@pytest.mark.asyncio
async def test_schedule_creates_task_for_write_cmd(mock_call_fn, mock_metrics):
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("set_property", {"path": "/Root/Node"})
    assert len(wd._pending) == 1
    wd.cancel_all()


def test_write_cmds_set():
    assert "set_property" in WRITE_CMDS
    assert "set_transform" in WRITE_CMDS
    assert "eval_js" in WRITE_CMDS
    assert "get_hierarchy" not in WRITE_CMDS


@pytest.mark.asyncio
async def test_lazy_cancel_same_path(mock_call_fn, mock_metrics):
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("set_property", {"path": "/Root/Node"})
    task1 = wd._pending.get("/Root/Node")
    wd.schedule("set_property", {"path": "/Root/Node"})
    task2 = wd._pending.get("/Root/Node")
    assert task1 is not task2
    await asyncio.sleep(0)
    assert task1.cancelled() or task1.done()
    wd.cancel_all()


@pytest.mark.asyncio
async def test_cancel_all_clears_pending(mock_call_fn, mock_metrics):
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("set_property", {"path": "/a"})
    wd.schedule("eval_js", {"path": "/b"})
    wd.cancel_all()
    assert len(wd._pending) == 0


@pytest.mark.asyncio
async def test_scan_records_error_on_console_error(mock_metrics):
    class FakeBridge:
        def get_console_messages(self, count, level):
            return ["error: NullReferenceException"]
    wd = Watchdog(None, mock_metrics, get_bridge=lambda: FakeBridge())
    wd._dedup = {}  # clear dedup
    orig_sleep = asyncio.sleep
    async def fast_sleep(t):
        pass
    asyncio.sleep = fast_sleep
    try:
        await wd._scan("set_property", {"path": "/Root/X"}, "/Root/X")
    finally:
        asyncio.sleep = orig_sleep
    assert any("watchdog" in c[0] for c in mock_metrics.calls)


@pytest.mark.asyncio
async def test_scan_no_error_on_clean_console(mock_call_fn, mock_metrics):
    wd = Watchdog(mock_call_fn, mock_metrics)
    orig_sleep = asyncio.sleep
    async def fast_sleep(t):
        pass
    asyncio.sleep = fast_sleep
    try:
        await wd._scan("set_property", {"path": "/Root/X"}, "/Root/X")
    finally:
        asyncio.sleep = orig_sleep
    assert len(mock_metrics.calls) == 0


@pytest.mark.asyncio
async def test_watchdog_schedules_simulate_touch(mock_call_fn, mock_metrics):
    """m1: simulate_touch must be in WRITE_CMDS."""
    assert "simulate_touch" in WRITE_CMDS
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("simulate_touch", {"x": 100, "y": 200})
    assert len(wd._pending) == 1
    wd.cancel_all()


def test_watchdog_skips_unknown_tool(mock_call_fn, mock_metrics):
    """m1: set_active is a ghost — not in WRITE_CMDS."""
    assert "set_active" not in WRITE_CMDS
    wd = Watchdog(mock_call_fn, mock_metrics)
    wd.schedule("set_active", {})
    assert len(wd._pending) == 0


def test_watchdog_schedules_simulate_key(mock_call_fn, mock_metrics):
    """m1: simulate_key must be in WRITE_CMDS."""
    assert "simulate_key" in WRITE_CMDS


@pytest.mark.asyncio
async def test_dedup_60s_window(mock_metrics):
    class FakeBridge:
        def get_console_messages(self, count, level):
            return ["error: crash"]
    wd = Watchdog(None, mock_metrics, get_bridge=lambda: FakeBridge())
    orig_sleep = asyncio.sleep
    async def fast_sleep(t):
        pass
    asyncio.sleep = fast_sleep
    try:
        # First scan: should record
        await wd._scan("set_property", {"path": "/X"}, "/X")
        first_count = len(mock_metrics.calls)
        # Second scan immediately: should be deduped
        await wd._scan("set_property", {"path": "/X"}, "/X")
        second_count = len(mock_metrics.calls)
    finally:
        asyncio.sleep = orig_sleep
    assert first_count == 1
    assert second_count == 1  # no new recording due to dedup
