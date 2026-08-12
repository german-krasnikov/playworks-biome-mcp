from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_bridge():
    b = Mock()
    b.send_cdp = AsyncMock(return_value={})
    return b


@pytest.fixture
def tools(mock_bridge):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.input_tools import register_input_tools
    mcp = FastMCP("test")
    reg = register_input_tools(mcp, lambda: mock_bridge, AsyncMock())
    return reg, mock_bridge


async def test_simulate_click_sends_two_cdp_events(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_click"]
    result = await fn(100, 200)
    calls = bridge.send_cdp.call_args_list
    assert calls[0][0] == ("Input.dispatchMouseEvent",)
    assert calls[0][1]["params"]["type"] == "mousePressed"
    assert calls[0][1]["params"]["x"] == 100
    assert calls[1][1]["params"]["type"] == "mouseReleased"
    assert result == "clicked (100, 200)"


async def test_simulate_touch_sends_touchstart_and_end(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_touch"]
    result = await fn(50, 75)
    calls = bridge.send_cdp.call_args_list
    assert calls[0][1]["params"]["type"] == "touchStart"
    assert calls[0][1]["params"]["touchPoints"] == [{"id": 0, "x": 50, "y": 75}]
    assert calls[1][1]["params"]["type"] == "touchEnd"
    assert calls[1][1]["params"]["touchPoints"] == []
    assert result == "touched (50, 75)"


async def test_simulate_key_sends_keydown_and_up(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_key"]
    result = await fn("Enter")
    calls = bridge.send_cdp.call_args_list
    assert calls[0][1]["params"]["type"] == "keyDown"
    assert calls[0][1]["params"]["key"] == "Enter"
    assert calls[1][1]["params"]["type"] == "keyUp"
    assert result == "key: Enter"


async def test_simulate_key_with_modifiers(tools):
    reg, bridge = tools
    fn, _ = reg["simulate_key"]
    await fn("s", modifiers=8)
    calls = bridge.send_cdp.call_args_list
    assert calls[0][1]["params"]["modifiers"] == 8
    assert calls[1][1]["params"]["modifiers"] == 8
