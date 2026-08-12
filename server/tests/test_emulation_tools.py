"""Tests for S4.2 emulation tools."""

import pytest


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


def make_bridge(calls):
    async def fake_send_cdp(method, params=None, **kw):
        calls.append((method, params or {}))
        return {}
    class FakeBridge:
        send_cdp = staticmethod(fake_send_cdp)
    return FakeBridge()


# --- registration ---

def test_emulation_tools_returns_3_entries():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    tools = register_emulation_tools(FakeMCP(), lambda: None, exposed=set())
    assert len(tools) == 3
    assert "set_cpu_throttle" in tools
    assert "set_device_metrics" in tools
    assert "clear_emulation" in tools


# --- cpu throttle ---

@pytest.mark.asyncio
async def test_cpu_throttle_params():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_emulation_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["set_cpu_throttle"]
    result = await fn(rate=6.0)
    assert any(m == "Emulation.setCPUThrottlingRate" for m, _ in calls)
    rate_params = next(p for m, p in calls if m == "Emulation.setCPUThrottlingRate")
    assert rate_params["rate"] == 6.0
    assert "6x" in result or "6.0" in result


@pytest.mark.asyncio
async def test_cpu_throttle_rejects_lt_1():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_emulation_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["set_cpu_throttle"]
    result = await fn(rate=0.5)
    assert "[INVALID]" in result
    assert not any("Emulation" in m for m, _ in calls)


# --- device metrics ---

@pytest.mark.asyncio
async def test_device_metrics_params():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_emulation_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["set_device_metrics"]
    result = await fn(width=390, height=844, dpr=3.0, mobile=True)
    assert any(m == "Emulation.setDeviceMetricsOverride" for m, _ in calls)
    p = next(p for m, p in calls if m == "Emulation.setDeviceMetricsOverride")
    assert p["width"] == 390
    assert p["height"] == 844
    assert p["deviceScaleFactor"] == 3.0
    assert "dpr" not in p
    assert p["mobile"] is True
    assert "clear_emulation" in result


# --- clear emulation ---

@pytest.mark.asyncio
async def test_clear_emulation_issues_both():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_emulation_tools(FakeMCP(), lambda: bridge, exposed=set())
    fn, _ = tools["clear_emulation"]
    result = await fn()
    methods = [m for m, _ in calls]
    assert "Emulation.setCPUThrottlingRate" in methods
    assert "Emulation.clearDeviceMetricsOverride" in methods
    # Rate must be 1 (reset)
    throttle_p = next(p for m, p in calls if m == "Emulation.setCPUThrottlingRate")
    assert throttle_p["rate"] == 1
    assert "cleared" in result


# --- degraded ---

@pytest.mark.asyncio
async def test_emulation_degraded_no_bridge():
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    tools = register_emulation_tools(FakeMCP(), lambda: None, exposed=set())
    for name in ("set_cpu_throttle", "set_device_metrics", "clear_emulation"):
        fn, _ = tools[name]
        result = await fn()
        assert "[DEGRADED]" in result


# --- read_only=False ---

def test_emulation_read_only_false():
    """All 3 tools must be registered as read_only=False."""
    from luna_mcp.tools import _HAS_ANNOTATIONS
    from luna_mcp.tools.emulation_tools import register_emulation_tools
    recorded = []
    class CaptureMCP:
        def tool(self, **kw):
            recorded.append(kw)
            def dec(fn): return fn
            return dec
    calls = []
    tools = register_emulation_tools(
        CaptureMCP(),
        lambda: make_bridge(calls),
        exposed={"set_cpu_throttle", "set_device_metrics", "clear_emulation"},
    )
    if _HAS_ANNOTATIONS:
        for kw in recorded:
            ann = kw.get("annotations")
            assert ann is not None, "annotations missing"
            assert ann.readOnlyHint is False, f"readOnlyHint should be False, got {ann.readOnlyHint}"
