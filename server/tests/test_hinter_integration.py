"""Integration tests for hinter + degradation layering in server composition."""
from unittest.mock import MagicMock

import pytest

from luna_mcp.degradation import GracefulDegradation
from luna_mcp.hinter import ToolHinter

# --- hinted() wrapper construction tests ---

def make_hinted(name: str, fn, hinter=None, degradation=None):
    """Replicate the _hinted() wrapper logic from server.py for isolated testing.
    TODO: use server._hinted directly when refactored to be importable."""
    _h = hinter or ToolHinter()
    _d = degradation

    async def wrapped(*args, **kw):
        if _d:
            deg = _d.check(name, kw)
            if deg:
                return deg
        result = await fn(*args, **kw)
        if isinstance(result, str):
            hint = _h.observe(name, kw, result)
            if hint:
                result = f"{result}\n{hint}"
        return result

    return wrapped


@pytest.mark.asyncio
async def test_hint_appears_in_response():
    """Hint appended to response after pattern detected."""
    call_count = 0

    async def mock_fn(**kw):
        nonlocal call_count
        call_count += 1
        return "[skipped get_hierarchy: budget exhausted]"

    h = ToolHinter()
    wrapped = make_hinted("get_hierarchy", mock_fn, hinter=h)

    # First call — records BUDGET tag but no hint yet (need prev call with same BUDGET)
    await wrapped()
    # Second call with same tool — budget-deaf fires
    result = await wrapped()
    assert "[HINT:" in result
    assert "budget-deaf" in result


@pytest.mark.asyncio
async def test_degradation_short_circuits_before_call():
    """Degradation returns early, inner fn not called."""
    called = False

    async def mock_fn(**kw):
        nonlocal called
        called = True
        return "data"

    bridge = MagicMock()
    bridge.connected = False
    d = GracefulDegradation(lambda: bridge, None, lambda: None)
    wrapped = make_hinted("get_hierarchy", mock_fn, degradation=d)

    result = await wrapped()
    assert not called
    assert "DEGRADED:chrome" in result


@pytest.mark.asyncio
async def test_no_hint_on_clean_output():
    """Normal tool output produces no hint."""
    async def mock_fn(**kw):
        return "Root\n  Btn\n  Text"

    h = ToolHinter()
    wrapped = make_hinted("get_hierarchy", mock_fn, hinter=h)
    result = await wrapped()
    assert "[HINT:" not in result


@pytest.mark.asyncio
async def test_hinter_wraps_after_gated():
    """Verify composition: hinted sees enriched output from gated (with [skipped] markers)."""
    h = ToolHinter()
    call_log = []

    async def inner(**kw):
        call_log.append("inner")
        return "[skipped eval_js: budget exhausted]"

    # Simulate gated wrapping inner
    async def gated_fn(**kw):
        return await inner(**kw)

    wrapped = make_hinted("eval_js", gated_fn, hinter=h)

    # After 1 call: inner result has BUDGET tag, hinter records it
    result1 = await wrapped(expression="x.y.z")
    # After 2nd identical: budget-deaf fires
    result2 = await wrapped(expression="x.y.z")

    assert "[HINT:budget-deaf" in result2
    assert "inner" in call_log


@pytest.mark.asyncio
async def test_skipped_response_not_hinted_for_already_emitted_marker():
    """Already-degraded response doesn't get duplicate HINT for the degradation itself."""
    h = ToolHinter()

    async def mock_fn(**kw):
        return "[DEGRADED:chrome:offline → run Chrome with --remote-debugging-port=9222]"

    wrapped = make_hinted("get_hierarchy", mock_fn, hinter=h)
    result = await wrapped()

    # Result should have at most one [HINT:...] block, not a cascade
    count = result.count("[HINT:")
    assert count <= 1
