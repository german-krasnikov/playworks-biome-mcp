"""Tests for S4.1 coverage_report and coverage_raw tools."""
from unittest.mock import patch

import pytest


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


FAKE_COVERAGE_RESULT = [
    {
        "scriptId": "s1",
        "url": "UnityScriptsCompiler.js",
        "functions": [
            {
                "functionName": "deadFn",
                "ranges": [{"startOffset": 6, "endOffset": 200, "count": 0}],
            }
        ],
    }
]

FAKE_SOURCE = "line1\n/*Game.Foo.Bar start*/\nline3\n"


def make_bridge(calls, take_result=None):
    _result = take_result if take_result is not None else FAKE_COVERAGE_RESULT

    async def fake_send_cdp(method, params=None, **kw):
        calls.append((method, params or {}))
        if method == "Profiler.takePreciseCoverage":
            return {"result": {"result": _result}}
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)

    return FakeBridge()


def make_mapper(source=FAKE_SOURCE):
    class FakeMapper:
        def find_script_id(self, name):
            return "s1"

        async def get_source(self, sid):
            return source

    return FakeMapper()


# --- registration ---

def test_coverage_tools_has_both():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    tools = register_coverage_tools(FakeMCP(), lambda: None, lambda: None, exposed=set())
    assert "coverage_report" in tools
    assert "coverage_raw" in tools


# --- CDP call order ---

@pytest.mark.asyncio
async def test_coverage_cdp_call_order():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: make_mapper(), exposed=set()
    )
    fn, _ = tools["coverage_report"]
    await fn(duration_ms=0, top=30)
    methods = [m for m, _ in calls]
    assert methods[0] == "Profiler.enable"
    assert methods[1] == "Profiler.startPreciseCoverage"
    assert "Profiler.takePreciseCoverage" in methods
    assert "Profiler.stopPreciseCoverage" in methods
    assert "Profiler.disable" in methods
    # startPreciseCoverage params
    p = next(p for m, p in calls if m == "Profiler.startPreciseCoverage")
    assert p.get("callCount") is False
    assert p.get("detailed") is True


@pytest.mark.asyncio
async def test_coverage_no_sleep_when_zero():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    sleep_calls = []
    calls = []
    bridge = make_bridge(calls)
    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: make_mapper(), exposed=set()
    )
    fn, _ = tools["coverage_report"]
    with patch("asyncio.sleep", side_effect=lambda s: sleep_calls.append(s)):
        await fn(duration_ms=0, top=30)
    assert sleep_calls == []


# --- maps dead method ---

@pytest.mark.asyncio
async def test_coverage_maps_dead_method():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []
    bridge = make_bridge(calls)
    mapper = make_mapper()
    get_source_calls = []
    find_script_calls = []
    original_get_source = mapper.get_source
    original_find = mapper.find_script_id

    async def tracked_get_source(sid):
        get_source_calls.append(sid)
        return await original_get_source(sid)

    def tracked_find(name):
        find_script_calls.append(name)
        return original_find(name)

    mapper.get_source = tracked_get_source
    mapper.find_script_id = tracked_find

    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: mapper, exposed=set()
    )
    fn, _ = tools["coverage_report"]
    result = await fn(duration_ms=0, top=30)
    assert "Game.Foo.Bar" in result
    assert "DEAD" in result
    assert find_script_calls  # _find_script_id was called
    assert get_source_calls   # _get_source was called


# --- unmapped graceful ---

@pytest.mark.asyncio
async def test_coverage_unmapped_graceful():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []
    bridge = make_bridge(calls)
    mapper = make_mapper(source="no markers here\n")
    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: mapper, exposed=set()
    )
    fn, _ = tools["coverage_report"]
    result = await fn(duration_ms=0, top=30)
    assert "UNMAPPED" in result or "no dead" in result.lower()


# --- minified no markers ---

@pytest.mark.asyncio
async def test_coverage_minified_no_markers():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []
    bridge = make_bridge(calls)
    mapper = make_mapper(source="minifiedcodenomarkers;")
    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: mapper, exposed=set()
    )
    fn, _ = tools["coverage_report"]
    result = await fn(duration_ms=0, top=30)
    # Should mention UNMAPPED or minified
    assert "UNMAPPED" in result or "no dead" in result.lower() or "minified" in result.lower()


# --- stop called on exception ---

@pytest.mark.asyncio
async def test_coverage_stop_called_on_exception():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []

    async def fake_send_cdp(method, params=None, **kw):
        calls.append(method)
        if method == "Profiler.takePreciseCoverage":
            raise RuntimeError("take error")
        return {}

    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)

    tools = register_coverage_tools(
        FakeMCP(), lambda: FakeBridge(), lambda: make_mapper(), exposed=set()
    )
    fn, _ = tools["coverage_report"]
    result = await fn(duration_ms=0)
    assert "Profiler.stopPreciseCoverage" in calls
    assert "Profiler.disable" in calls
    assert "[DEGRADED]" in result


# --- degraded ---

@pytest.mark.asyncio
async def test_coverage_degraded_no_bridge():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    tools = register_coverage_tools(FakeMCP(), lambda: None, lambda: None, exposed=set())
    fn, _ = tools["coverage_report"]
    result = await fn()
    assert "[DEGRADED]" in result


# --- output never returns blob ---

@pytest.mark.asyncio
async def test_coverage_never_returns_blob():
    from luna_mcp.tools.coverage_tools import register_coverage_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_coverage_tools(
        FakeMCP(), lambda: bridge, lambda: make_mapper(), exposed=set()
    )
    fn, _ = tools["coverage_report"]
    result = await fn(duration_ms=0, top=30)
    assert len(result) < 4000
    assert "startOffset" not in result
    assert "ranges" not in result
