"""Tests for S4.5 network condition tools."""
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


async def noop_ensure(): pass


# --- registration ---

def test_netcond_tools_returns_3_entries():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    tools = register_netcond_tools(FakeMCP(), lambda: None, noop_ensure, exposed=set())
    assert len(tools) == 3
    assert "set_network" in tools
    assert "block_urls" in tools
    assert "clear_network" in tools


# --- set_network ---

@pytest.mark.asyncio
async def test_set_network_offline_params():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["set_network"]
    result = await fn(profile="offline")
    methods = [m for m, _ in calls]
    assert "Network.emulateNetworkConditions" in methods
    p = next(p for m, p in calls if m == "Network.emulateNetworkConditions")
    assert p["offline"] is True
    assert p["downloadThroughput"] == 0
    assert p["uploadThroughput"] == 0
    assert "offline" in result


@pytest.mark.asyncio
async def test_set_network_3g_preset():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["set_network"]
    result = await fn(profile="3g")
    p = next(p for m, p in calls if m == "Network.emulateNetworkConditions")
    assert p["latency"] == 400
    assert p["downloadThroughput"] == 400_000
    assert p["uploadThroughput"] == 400_000


@pytest.mark.asyncio
async def test_set_network_invalid_profile():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["set_network"]
    result = await fn(profile="dialup")
    assert "[INVALID" in result
    assert not any("Network.emulate" in m for m, _ in calls)


@pytest.mark.asyncio
async def test_set_network_enables_network_first():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["set_network"]
    await fn(profile="offline")
    methods = [m for m, _ in calls]
    enable_idx = methods.index("Network.enable")
    emulate_idx = methods.index("Network.emulateNetworkConditions")
    assert enable_idx < emulate_idx


# --- block_urls ---

@pytest.mark.asyncio
async def test_block_urls_splits_csv():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["block_urls"]
    result = await fn(patterns_csv="*a*, *b*")
    p = next(p for m, p in calls if m == "Network.setBlockedURLs")
    assert p["urls"] == ["*a*", "*b*"]
    assert "2" in result


@pytest.mark.asyncio
async def test_block_urls_enables_network_first():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["block_urls"]
    await fn(patterns_csv="*cdn*")
    methods = [m for m, _ in calls]
    assert "Network.enable" in methods
    enable_idx = methods.index("Network.enable")
    block_idx = methods.index("Network.setBlockedURLs")
    assert enable_idx < block_idx


@pytest.mark.asyncio
async def test_clear_network_enables_network_first():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["clear_network"]
    await fn()
    methods = [m for m, _ in calls]
    assert "Network.enable" in methods
    enable_idx = methods.index("Network.enable")
    emulate_idx = methods.index("Network.emulateNetworkConditions")
    assert enable_idx < emulate_idx


# --- clear_network ---

@pytest.mark.asyncio
async def test_clear_network_resets_both():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    calls = []
    bridge = make_bridge(calls)
    tools = register_netcond_tools(FakeMCP(), lambda: bridge, noop_ensure, exposed=set())
    fn, _ = tools["clear_network"]
    result = await fn()
    methods = [m for m, _ in calls]
    assert "Network.emulateNetworkConditions" in methods
    assert "Network.setBlockedURLs" in methods
    # emulate before setBlockedURLs
    assert methods.index("Network.emulateNetworkConditions") < methods.index("Network.setBlockedURLs")
    # online preset: offline=False, download=-1
    p = next(p for m, p in calls if m == "Network.emulateNetworkConditions")
    assert p["offline"] is False
    assert p["downloadThroughput"] == -1
    # empty urls
    p2 = next(p for m, p in calls if m == "Network.setBlockedURLs")
    assert p2["urls"] == []
    assert "reset" in result


# --- degraded ---

@pytest.mark.asyncio
async def test_netcond_degraded_no_bridge():
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    tools = register_netcond_tools(FakeMCP(), lambda: None, noop_ensure, exposed=set())
    for name in ("set_network", "block_urls", "clear_network"):
        fn, _ = tools[name]
        result = await fn()
        assert "[DEGRADED]" in result


# --- read_only=False ---

def test_netcond_read_only_false():
    from luna_mcp.tools import _HAS_ANNOTATIONS
    from luna_mcp.tools.netcond_tools import register_netcond_tools
    recorded = []
    class CaptureMCP:
        def tool(self, **kw):
            recorded.append(kw)
            def dec(fn): return fn
            return dec
    calls = []
    register_netcond_tools(
        CaptureMCP(),
        lambda: make_bridge(calls),
        noop_ensure,
        exposed={"set_network", "block_urls", "clear_network"},
    )
    if _HAS_ANNOTATIONS:
        for kw in recorded:
            ann = kw.get("annotations")
            assert ann is not None
            assert ann.readOnlyHint is False
