"""Tests for events_tools — watch, stream_until, get_events, set_event_filter."""
import asyncio
from unittest.mock import AsyncMock, MagicMock


def _make_bus():
    from luna_mcp.cdp_bridge import EventBus
    return EventBus()


def _make_bridge(bus=None):
    b = MagicMock()
    b.bus = bus or _make_bus()
    return b


# ---- watch ----

async def test_watch_finds_console_message():
    """watch returns matched text after event arrives via bus."""
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bus = _make_bus()
    bridge = _make_bridge(bus)
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["watch"]

    async def inject():
        await asyncio.sleep(0.05)
        bus.publish("console", {"text": "player died", "level": "I"})

    asyncio.create_task(inject())
    result = await fn(kinds="console", pattern="player", timeout_ms=2000, max_events=1)
    assert "player" in result
    assert "[TIMEOUT" not in result


async def test_watch_timeout_returns_partial():
    """watch returns TIMEOUT marker when no match arrives."""
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bus = _make_bus()
    bridge = _make_bridge(bus)
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["watch"]

    result = await fn(kinds="console", pattern="IMPOSSIBLE_XYZ", timeout_ms=200, max_events=1)
    assert "[TIMEOUT" in result


async def test_watch_invalid_pattern():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = _make_bridge()
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["watch"]

    result = await fn(kinds="console", pattern="[invalid", timeout_ms=500)
    assert "[INVALID" in result


async def test_watch_invalid_kinds():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = _make_bridge()
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["watch"]

    result = await fn(kinds="bogus_kind", pattern=".*", timeout_ms=500)
    assert "[INVALID" in result


async def test_watch_no_bridge():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: None, set())
    fn, _ = tools["watch"]

    result = await fn(kinds="console", pattern=".*", timeout_ms=200)
    assert "[DEGRADED" in result


# ---- stream_until ----

async def test_stream_until_returns_on_truthy():
    """stream_until resolves when eval returns truthy on 3rd call."""
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = MagicMock()
    bridge.bus = _make_bus()
    call_count = 0

    async def fake_eval(expr):
        nonlocal call_count
        call_count += 1
        return "true" if call_count >= 3 else "false"

    bridge.eval = fake_eval
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["stream_until"]

    result = await fn(condition_js="someCondition()", timeout_ms=3000, poll_ms=50)
    assert result.startswith("OK")
    assert call_count >= 3


async def test_stream_until_timeout():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = MagicMock()
    bridge.bus = _make_bus()
    bridge.eval = AsyncMock(return_value="false")

    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["stream_until"]

    result = await fn(condition_js="false", timeout_ms=300, poll_ms=50)
    assert "TIMEOUT" in result


# ---- get_events ----

async def test_get_events_returns_snapshot():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bus = _make_bus()
    bus.publish("console", {"text": "hello", "level": "I"})
    bus.publish("console", {"text": "world", "level": "W"})
    bridge = _make_bridge(bus)

    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["get_events"]

    result = await fn(kind="console", count=10)
    assert "hello" in result
    assert "world" in result


async def test_get_events_kind_validation():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = _make_bridge()
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["get_events"]

    result = await fn(kind="unknown_kind", count=10)
    assert "[INVALID" in result


# ---- set_event_filter ----

async def test_set_event_filter_compiles():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bus = _make_bus()
    bridge = _make_bridge(bus)
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["set_event_filter"]

    result = await fn(kind="console", drop_regex=r"\[noise\]")
    assert "OK" in result
    assert "console" in bus._filters


async def test_set_event_filter_clears():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bus = _make_bus()
    bus.set_filter("console", r"noise")
    bridge = _make_bridge(bus)

    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["set_event_filter"]

    result = await fn(kind="console", drop_regex="")
    assert "OK" in result
    assert "console" not in bus._filters


async def test_set_event_filter_bad_regex():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = _make_bridge()
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["set_event_filter"]

    result = await fn(kind="console", drop_regex="[bad")
    assert "[INVALID" in result


async def test_set_event_filter_unknown_kind():
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.events_tools import register_events_tools

    bridge = _make_bridge()
    mcp = FastMCP("test")
    tools = register_events_tools(mcp, lambda: bridge, set())
    fn, _ = tools["set_event_filter"]

    result = await fn(kind="bogus", drop_regex="whatever")
    assert "[INVALID" in result
