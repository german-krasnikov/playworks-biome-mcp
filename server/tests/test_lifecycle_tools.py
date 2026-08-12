"""Tests for S3.3 lifecycle waiter + stream tools."""
import pathlib

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


def make_call_fn(return_values: dict):
    """Create a call_fn mock that returns configured values per method name."""
    async def call_fn(method, *args):
        return return_values.get(method, "")
    return call_fn


# --- wait_for_lifecycle ---

@pytest.mark.asyncio
async def test_wait_already_fired():
    call_fn = make_call_fn({"waitForLunaEvent": "already:1200"})
    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["wait_for_lifecycle"]
    result = await fn("GameStarted")
    assert result == "fired (already, t=1200ms)"


@pytest.mark.asyncio
async def test_wait_fired():
    call_fn = make_call_fn({"waitForLunaEvent": "fired:1350"})
    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["wait_for_lifecycle"]
    result = await fn("GameStarted")
    assert result == "fired (t=1350ms)"


@pytest.mark.asyncio
async def test_wait_timeout():
    call_fn = make_call_fn({"waitForLunaEvent": "timeout:10000"})
    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["wait_for_lifecycle"]
    result = await fn("GameStarted", timeout_ms=10000)
    assert "TIMEOUT" in result
    assert "10000" in result
    assert "GameStarted" in result


@pytest.mark.asyncio
async def test_wait_event_name_validated():
    """Empty event name → INVALID without calling JS."""
    called = []

    async def call_fn(method, *args):
        called.append(method)
        return ""

    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["wait_for_lifecycle"]
    result = await fn("")
    assert "INVALID" in result
    assert not called


@pytest.mark.asyncio
async def test_wait_timeout_zero_normalized():
    """timeout_ms=0 must be normalised to >=1 before being passed to call_fn."""
    received = []

    async def call_fn(method, *args):
        received.append((method, args))
        return "fired:1"

    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["wait_for_lifecycle"]
    await fn("GameStarted", timeout_ms=0)
    wait_calls = [(m, a) for m, a in received if m == "waitForLunaEvent"]
    assert wait_calls, "waitForLunaEvent was not called"
    timeout_arg = wait_calls[0][1][1]  # second positional arg
    assert timeout_arg >= 1, f"timeout_ms should be >=1, got {timeout_arg}"


# --- lifecycle_events ---

@pytest.mark.asyncio
async def test_lifecycle_events_parse():
    responses = {
        "tapLifecycle": "already",
        "getLifecycleEvents": "luna:started|1200\nGameEnded|5000",
    }
    call_fn = make_call_fn(responses)
    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["lifecycle_events"]
    result = await fn(0)
    lines = [l for l in result.strip().split("\n") if l]
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_lifecycle_events_empty():
    responses = {
        "tapLifecycle": "already",
        "getLifecycleEvents": "",
    }
    call_fn = make_call_fn(responses)
    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["lifecycle_events"]
    result = await fn(0)
    assert result == "[no lifecycle events]"


@pytest.mark.asyncio
async def test_lifecycle_degraded_no_helpers():
    """call_fn raising → DEGRADED prefix, no crash."""
    async def call_fn(method, *args):
        raise RuntimeError("no helpers")

    from luna_mcp.tools.lifecycle_tools import register_lifecycle_tools
    reg = register_lifecycle_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["lifecycle_events"]
    result = await fn(0)
    assert result.startswith("[DEGRADED:lifecycle")


# --- JS presence ---

def test_js_waitForLunaEvent_present():
    src = JS_PATH.read_text()
    assert "waitForLunaEvent:" in src


def test_js_tapLifecycle_present():
    src = JS_PATH.read_text()
    assert "tapLifecycle:" in src


def test_js_getLifecycleEvents_present():
    src = JS_PATH.read_text()
    assert "getLifecycleEvents:" in src


def test_js_lunaStartup_present():
    src = JS_PATH.read_text()
    assert "lunaStartup" in src


def test_js_luna_lc_hooked_present():
    src = JS_PATH.read_text()
    assert "__luna_lc_hooked" in src


def test_js_lifecycle_names_present():
    src = JS_PATH.read_text()
    assert "OnStart" in src
    assert "GameStarted" in src
    assert "GameEnded" in src
