"""Tests for S4.4 heap sampling tools."""
from unittest.mock import patch

import pytest


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


SAMPLE_PROFILE = {
    "head": {
        "callFrame": {"functionName": "root", "url": "", "lineNumber": 0},
        "selfSize": 0,
        "children": [
            {
                "callFrame": {"functionName": "allocBig", "url": "main.js", "lineNumber": 10},
                "selfSize": 200000,
                "children": [
                    {
                        "callFrame": {"functionName": "allocSmall", "url": "main.js", "lineNumber": 20},
                        "selfSize": 50000,
                        "children": [],
                    }
                ],
            },
            {
                "callFrame": {"functionName": "allocBig", "url": "main.js", "lineNumber": 10},
                "selfSize": 100000,
                "children": [],
            },
        ],
    }
}


def make_bridge(calls, profile=SAMPLE_PROFILE):
    async def fake_send_cdp(method, params=None, **kw):
        calls.append((method, params or {}))
        if method == "HeapProfiler.stopSampling":
            return {"result": {"profile": profile}}
        return {}
    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)
    return FakeBridge()


# --- registration ---

def test_heap_tools_returns_1_entry():
    from luna_mcp.tools.heap_tools import register_heap_tools
    tools = register_heap_tools(FakeMCP(), lambda: None, exposed=set())
    assert "heap_sample" in tools


# --- CDP order ---

@pytest.mark.asyncio
async def test_heap_cdp_order():
    from luna_mcp.tools.heap_tools import register_heap_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_heap_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["heap_sample"]
    await fn(duration_ms=0, top=5)
    methods = [m for m, _ in calls]
    assert methods[0] == "HeapProfiler.enable"
    assert methods[1] == "HeapProfiler.startSampling"
    assert "HeapProfiler.stopSampling" in methods
    assert "HeapProfiler.disable" in methods
    # startSampling must have samplingInterval
    p = next(p for m, p in calls if m == "HeapProfiler.startSampling")
    assert p.get("samplingInterval") == 32768


@pytest.mark.asyncio
async def test_heap_no_sleep_when_zero():
    from luna_mcp.tools.heap_tools import register_heap_tools
    sleep_calls = []
    calls = []
    bridge = make_bridge(calls)
    tools = register_heap_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["heap_sample"]
    with patch("asyncio.sleep", side_effect=lambda s: sleep_calls.append(s)) as _:
        await fn(duration_ms=0, top=5)
    assert sleep_calls == []


# --- summary from fixture ---

@pytest.mark.asyncio
async def test_heap_summary_from_fixture():
    from luna_mcp.tools.heap_tools import register_heap_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_heap_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["heap_sample"]
    result = await fn(duration_ms=0, top=15)
    # allocBig sums to 300KB (200000+100000), allocSmall is 50KB
    assert "allocBig" in result
    # no raw internal keys
    assert "children" not in result
    assert "callFrame" not in result
    # allocBig must appear before allocSmall (sorted desc)
    assert result.index("allocBig") < result.index("allocSmall")


# --- empty profile ---

@pytest.mark.asyncio
async def test_heap_empty_profile():
    from luna_mcp.tools.heap_tools import register_heap_tools
    calls = []

    async def fake_send_cdp(method, params=None, **kw):
        calls.append((method, params or {}))
        if method == "HeapProfiler.stopSampling":
            return {"result": {"profile": {}}}
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)

    tools = register_heap_tools(FakeMCP(), lambda: FakeBridge(), exposed=set())
    fn, _ = tools["heap_sample"]
    result = await fn(duration_ms=0)
    assert "no allocation" in result.lower()


# --- stop called on exception ---

@pytest.mark.asyncio
async def test_heap_stop_on_exception():
    from luna_mcp.tools.heap_tools import register_heap_tools
    calls = []

    async def fake_send_cdp(method, params=None, **kw):
        calls.append(method)
        if method == "HeapProfiler.stopSampling":
            raise RuntimeError("stop error")
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)

    tools = register_heap_tools(FakeMCP(), lambda: FakeBridge(), exposed=set())
    fn, _ = tools["heap_sample"]
    result = await fn(duration_ms=0)
    assert "HeapProfiler.disable" in calls
    assert "HeapProfiler.stopSampling" in calls


# --- degraded ---

@pytest.mark.asyncio
async def test_heap_degraded_no_bridge():
    from luna_mcp.tools.heap_tools import register_heap_tools
    tools = register_heap_tools(FakeMCP(), lambda: None, exposed=set())
    fn, _ = tools["heap_sample"]
    result = await fn()
    assert "[DEGRADED]" in result


# --- output capped ---

@pytest.mark.asyncio
async def test_heap_output_capped():
    """Many allocators should only show top N."""
    from luna_mcp.tools.heap_tools import register_heap_tools

    # Build a profile with 50 children
    children = [
        {
            "callFrame": {"functionName": f"fn{i}", "url": "x.js", "lineNumber": i},
            "selfSize": (50 - i) * 1000,
            "children": [],
        }
        for i in range(50)
    ]
    big_profile = {"head": {"callFrame": {"functionName": "root", "url": "", "lineNumber": 0}, "selfSize": 0, "children": children}}

    calls = []

    async def fake_send_cdp(method, params=None, **kw):
        calls.append(method)
        if method == "HeapProfiler.stopSampling":
            return {"result": {"profile": big_profile}}
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)

    tools = register_heap_tools(FakeMCP(), lambda: FakeBridge(), exposed=set())
    fn, _ = tools["heap_sample"]
    result = await fn(duration_ms=0, top=5)
    lines = [l for l in result.splitlines() if l.strip()]
    # 5 data lines + 1 truncation line = 6 max
    assert len(lines) <= 6
    assert "more" in result
