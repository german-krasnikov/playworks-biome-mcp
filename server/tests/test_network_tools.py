from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_bridge():
    b = Mock()
    b.send_cdp = AsyncMock(return_value={})
    b._network_requests = []
    b.get_network_requests = Mock(return_value=[])
    return b


@pytest.fixture
def tools(mock_bridge):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.network_tools import register_network_tools
    mcp = FastMCP("test")
    send_fn = AsyncMock(return_value="n/a")
    reg = register_network_tools(mcp, send_fn, lambda: mock_bridge, AsyncMock())
    return reg, mock_bridge, send_fn


# get_network_requests
async def test_get_network_requests_no_filter(tools):
    reg, bridge, _ = tools
    bridge.get_network_requests = Mock(return_value=[
        {"url": "http://a.com/api", "method": "GET", "status": 200},
    ])
    fn, _ = reg["get_network_requests"]
    result = await fn()
    assert "http://a.com/api" in result


async def test_get_network_requests_with_filter(tools):
    reg, bridge, _ = tools
    bridge.get_network_requests = Mock(side_effect=lambda count, filter_str="": [
        r for r in [
            {"url": "http://api.example.com/data", "method": "GET", "status": 200},
            {"url": "http://other.com/img", "method": "GET", "status": 200},
        ] if not filter_str or filter_str in r["url"]
    ])
    fn, _ = reg["get_network_requests"]
    result = await fn(filter_str="api")
    assert "api.example.com" in result
    assert "other.com" not in result


async def test_get_network_requests_empty(tools):
    reg, bridge, _ = tools
    bridge.get_network_requests = Mock(return_value=[])
    fn, _ = reg["get_network_requests"]
    result = await fn()
    assert result == "(no requests)"


# get_memory_info
async def test_get_memory_info_returns_kb(tools):
    reg, bridge, send_fn = tools
    bridge.send_cdp = AsyncMock(return_value={"result": {"usedSize": 1048576, "totalSize": 2097152}})
    fn, _ = reg["get_memory_info"]
    result = await fn()
    assert "1024KB" in result
    assert "2048KB" in result


async def test_get_memory_info_gpu_fallback(tools):
    reg, bridge, send_fn = tools
    bridge.send_cdp = AsyncMock(return_value={"result": {"usedSize": 512000, "totalSize": 1024000}})
    send_fn.side_effect = RuntimeError("no gpu")
    fn, _ = reg["get_memory_info"]
    result = await fn()
    assert "heap_used" in result
    assert "gpu" not in result


# trigger_gc
async def test_trigger_gc_returns_freed(tools):
    reg, bridge, _ = tools
    bridge.send_cdp = AsyncMock(side_effect=[
        {"result": {"usedSize": 2048000, "totalSize": 4096000}},  # before
        {},  # collectGarbage
        {"result": {"usedSize": 1024000, "totalSize": 4096000}},  # after
    ])
    fn, _ = reg["trigger_gc"]
    result = await fn()
    assert "before" in result
    assert "after" in result
    assert "freed" in result


async def test_trigger_gc_calls_collect_garbage(tools):
    reg, bridge, _ = tools
    bridge.send_cdp = AsyncMock(side_effect=[
        {"result": {"usedSize": 1000, "totalSize": 2000}},
        {},
        {"result": {"usedSize": 800, "totalSize": 2000}},
    ])
    fn, _ = reg["trigger_gc"]
    await fn()
    methods = [c[0][0] for c in bridge.send_cdp.call_args_list]
    assert "HeapProfiler.collectGarbage" in methods


# CDPBridge network buffering
def test_parse_network_event_request():
    from luna_mcp.cdp_bridge import CDPBridge
    b = CDPBridge()
    event = {"method": "Network.requestWillBeSent", "params": {
        "requestId": "1", "type": "XHR",
        "request": {"url": "http://example.com/api", "method": "POST"}
    }}
    result = b._parse_network_event(event)
    assert result is not None
    assert result["url"] == "http://example.com/api"
    assert result["method"] == "POST"
    assert result["status"] == "pending"


def test_parse_network_event_response_updates_in_place():
    from luna_mcp.cdp_bridge import CDPBridge
    b = CDPBridge()
    b._network_requests = [{"id": "1", "url": "http://x.com", "method": "GET", "status": "pending"}]
    event = {"method": "Network.responseReceived", "params": {
        "requestId": "1",
        "response": {"status": 200, "mimeType": "application/json"}
    }}
    result = b._parse_network_event(event)
    assert result is None  # updated in place
    assert b._network_requests[0]["status"] == 200


def test_get_network_requests_filter():
    from luna_mcp.cdp_bridge import CDPBridge
    b = CDPBridge()
    b._network_requests = [
        {"id": "1", "url": "http://api.example.com/data", "method": "GET", "status": 200},
        {"id": "2", "url": "http://cdn.example.com/img.png", "method": "GET", "status": 200},
    ]
    result = b.get_network_requests(50, "api")
    assert len(result) == 1
    assert result[0]["url"] == "http://api.example.com/data"
