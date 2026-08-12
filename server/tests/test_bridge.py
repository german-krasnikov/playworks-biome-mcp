import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import websockets

from luna_mcp.cdp_bridge import CDPBridge

# ── Step 1: Pure logic ──────────────────────────────────────────────────────

def test_find_page_returns_first_page_type():
    bridge = CDPBridge()
    pages = [
        {"type": "other", "title": "x", "url": "x"},
        {"type": "page", "title": "Luna", "url": "http://a", "webSocketDebuggerUrl": "ws://a"},
    ]
    assert bridge._find_page(pages) == pages[1]


def test_find_page_with_filter():
    bridge = CDPBridge()
    pages = [
        {"type": "page", "title": "Other", "url": "http://other"},
        {"type": "page", "title": "Luna Build", "url": "http://luna", "webSocketDebuggerUrl": "ws://luna"},
    ]
    assert bridge._find_page(pages, "luna") == pages[1]


def test_find_page_empty_list():
    bridge = CDPBridge()
    assert bridge._find_page([]) is None


def test_find_page_filter_no_match_returns_none():
    bridge = CDPBridge()
    pages = [{"type": "page", "title": "Other", "url": "http://other"}]
    assert bridge._find_page(pages, "luna") is None


def test_connected_false_when_ws_none():
    bridge = CDPBridge()
    assert bridge.connected is False


def test_connected_true_when_ws_open():
    bridge = CDPBridge()
    ws = Mock()
    ws.state = 1  # OPEN
    bridge._ws = ws
    assert bridge.connected is True


def test_connected_false_when_ws_closed():
    bridge = CDPBridge()
    ws = Mock()
    ws.closed = True
    bridge._ws = ws
    assert bridge.connected is False


# ── Step 2: Async core ──────────────────────────────────────────────────────

@pytest.fixture
def bridge_with_ws():
    bridge = CDPBridge()
    bridge._ws = AsyncMock()
    bridge._ws.closed = False
    return bridge


async def test_send_cdp_increments_id(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()

    # Resolve future immediately after send
    async def fake_send(msg):
        data = json.loads(msg)
        msg_id = data["id"]
        loop.call_soon(bridge._pending[msg_id].set_result, {"id": msg_id, "result": {}})

    bridge._ws.send = fake_send

    await bridge.send_cdp("Runtime.evaluate", {})
    assert bridge._counter == 1
    await bridge.send_cdp("Runtime.evaluate", {})
    assert bridge._counter == 2


async def test_eval_returns_value(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()

    async def fake_send(msg):
        data = json.loads(msg)
        mid = data["id"]
        response = {"id": mid, "result": {"result": {"type": "string", "value": "hello"}}}
        loop.call_soon(bridge._pending[mid].set_result, response)

    bridge._ws.send = fake_send
    result = await bridge.eval("'hello'")
    assert result == "hello"


async def test_eval_returns_empty_for_undefined(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()

    async def fake_send(msg):
        data = json.loads(msg)
        mid = data["id"]
        response = {"id": mid, "result": {"result": {"type": "undefined"}}}
        loop.call_soon(bridge._pending[mid].set_result, response)

    bridge._ws.send = fake_send
    result = await bridge.eval("undefined")
    assert result == ""


async def test_eval_raises_on_js_error(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()

    async def fake_send(msg):
        data = json.loads(msg)
        mid = data["id"]
        response = {"id": mid, "result": {"exceptionDetails": {"text": "ReferenceError"}}}
        loop.call_soon(bridge._pending[mid].set_result, response)

    bridge._ws.send = fake_send
    with pytest.raises(RuntimeError, match="ReferenceError"):
        await bridge.eval("badVar")


async def test_eval_raises_on_cdp_error(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()

    async def fake_send(msg):
        data = json.loads(msg)
        mid = data["id"]
        response = {"id": mid, "error": {"code": -32000, "message": "Cannot find context"}}
        loop.call_soon(bridge._pending[mid].set_result, response)

    bridge._ws.send = fake_send
    with pytest.raises(RuntimeError, match="Cannot find context"):
        await bridge.eval("x")


async def test_eval_timeout_raises(bridge_with_ws):
    bridge = bridge_with_ws
    bridge._ws.send = AsyncMock()  # send succeeds but no response comes
    with pytest.raises(asyncio.TimeoutError):
        await bridge.eval("slow", timeout=0.05)


async def test_screenshot_returns_bytes(bridge_with_ws):
    import base64
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()
    png_bytes = b"\x89PNG\r\n"
    encoded = base64.b64encode(png_bytes).decode()

    async def fake_send(msg):
        data = json.loads(msg)
        mid = data["id"]
        response = {"id": mid, "result": {"data": encoded}}
        loop.call_soon(bridge._pending[mid].set_result, response)

    bridge._ws.send = fake_send
    result = await bridge.screenshot()
    assert result == png_bytes


# ── Step 3: Read loop ───────────────────────────────────────────────────────

async def test_read_loop_resolves_futures():
    bridge = CDPBridge()
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bridge._pending[1] = future

    response = json.dumps({"id": 1, "result": {"ok": True}})

    async def fake_iter():
        yield response

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert future.done()
    assert future.result() == {"id": 1, "result": {"ok": True}}


async def test_read_loop_queues_events():
    bridge = CDPBridge()
    event = json.dumps({"method": "Console.messageAdded", "params": {}})

    async def fake_iter():
        yield event

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert not bridge._events.empty()
    queued = bridge._events.get_nowait()
    assert queued["method"] == "Console.messageAdded"


async def test_read_loop_captures_debugger_paused():
    bridge = CDPBridge()
    call_frames = [{"functionName": "foo"}]
    event = json.dumps({"method": "Debugger.paused", "params": {"callFrames": call_frames}})

    async def fake_iter():
        yield event

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert bridge._debugger_paused == {"callFrames": call_frames}


async def test_read_loop_clears_debugger_on_resumed():
    bridge = CDPBridge()
    bridge._debugger_paused = {"callFrames": []}
    event = json.dumps({"method": "Debugger.resumed", "params": {}})

    async def fake_iter():
        yield event

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert bridge._debugger_paused is None


async def test_read_loop_handles_disconnect():
    bridge = CDPBridge()
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bridge._pending[1] = future

    async def fake_iter():
        raise websockets.ConnectionClosed(None, None)
        yield  # make it a generator

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert future.done()
    assert isinstance(future.exception(), ConnectionError)


# ── Step 4: Connect / close ─────────────────────────────────────────────────

async def test_discover_pages_makes_http_request():
    bridge = CDPBridge()
    pages_data = [{"type": "page", "url": "http://a"}]

    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=pages_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = Mock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("luna_mcp.cdp_bridge.aiohttp.ClientSession", return_value=mock_session):
        result = await bridge._discover_pages()

    assert result == pages_data


async def test_connect_opens_websocket():
    bridge = CDPBridge()
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://localhost:9222/page/1"}]

    mock_ws = AsyncMock()
    mock_ws.closed = False

    async def fake_connect(*args, **kwargs):
        return mock_ws

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_connect):
        await bridge.connect()

    assert bridge._ws is mock_ws
    assert bridge._reader_task is not None
    # cleanup
    bridge._reader_task.cancel()


async def test_close_cancels_reader():
    bridge = CDPBridge()
    bridge._ws = AsyncMock()
    bridge._ws.closed = False

    task = asyncio.create_task(asyncio.sleep(100))
    bridge._reader_task = task

    await bridge.close()
    assert task.cancelled()
    assert bridge._reader_task is None


async def test_close_closes_ws():
    bridge = CDPBridge()
    mock_ws = AsyncMock()
    mock_ws.closed = False
    bridge._ws = mock_ws

    await bridge.close()
    mock_ws.close.assert_called_once()
    assert bridge._ws is None


# ── Step 5: Console capture ─────────────────────────────────────────────────

async def test_enable_console_sends_commands(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()
    sent = []

    async def fake_send(msg):
        data = json.loads(msg)
        sent.append(data["method"])
        loop.call_soon(bridge._pending[data["id"]].set_result, {"id": data["id"], "result": {}})

    bridge._ws.send = fake_send
    await bridge.enable_console()
    assert "Console.enable" in sent
    assert "Runtime.enable" in sent


def test_parse_console_message_added():
    bridge = CDPBridge()
    event = {
        "method": "Console.messageAdded",
        "params": {"message": {"text": "NullRef at Player.js:47", "level": "error", "timestamp": 1234567890123}},
    }
    result = bridge._parse_console_event(event)
    assert result == {"level": "E", "timestamp": 1234567890123, "text": "NullRef at Player.js:47"}


def test_parse_runtime_console_api_called():
    bridge = CDPBridge()
    event = {
        "method": "Runtime.consoleAPICalled",
        "params": {"type": "warning", "args": [{"value": "Physics issue"}], "timestamp": 9876543210.0},
    }
    result = bridge._parse_console_event(event)
    assert result == {"level": "W", "timestamp": 9876543210.0, "text": "Physics issue"}


def test_parse_runtime_console_api_log():
    bridge = CDPBridge()
    event = {
        "method": "Runtime.consoleAPICalled",
        "params": {"type": "log", "args": [{"value": "hello"}, {"value": "world"}], "timestamp": 0.0},
    }
    result = bridge._parse_console_event(event)
    assert result["level"] == "I"
    assert result["text"] == "hello world"


def test_parse_ignores_non_console_events():
    bridge = CDPBridge()
    event = {"method": "Page.loadEventFired", "params": {}}
    assert bridge._parse_console_event(event) is None


def test_get_console_messages_drains_queue():
    bridge = CDPBridge()
    event = {
        "method": "Console.messageAdded",
        "params": {"message": {"text": "hello", "level": "log", "timestamp": 0}},
    }
    bridge._events.put_nowait(event)
    msgs = bridge.get_console_messages()
    assert len(msgs) == 1
    assert msgs[0]["text"] == "hello"
    assert bridge._events.empty()


def test_get_console_messages_filters_by_level():
    bridge = CDPBridge()
    bridge._console_messages = [
        {"level": "E", "timestamp": 1, "text": "err"},
        {"level": "I", "timestamp": 2, "text": "info"},
        {"level": "W", "timestamp": 3, "text": "warn"},
    ]
    result = bridge.get_console_messages(level="E")
    assert all(m["level"] == "E" for m in result)
    assert len(result) == 1


def test_get_console_messages_limits_count():
    bridge = CDPBridge()
    bridge._console_messages = [{"level": "I", "timestamp": i, "text": f"msg{i}"} for i in range(20)]
    result = bridge.get_console_messages(count=5)
    assert len(result) == 5
    assert result[-1]["text"] == "msg19"  # last 5


def test_console_ring_buffer_max_500():
    bridge = CDPBridge()
    bridge._console_messages = [{"level": "I", "timestamp": i, "text": f"m{i}"} for i in range(500)]
    # Add one more via queue
    bridge._events.put_nowait({
        "method": "Console.messageAdded",
        "params": {"message": {"text": "new", "level": "log", "timestamp": 999}},
    })
    bridge.get_console_messages()
    assert len(bridge._console_messages) == 500


# ── Phase 4: Reconnection ───────────────────────────────────────────────────

async def test_reconnect_saves_page_filter():
    bridge = CDPBridge()
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    async def fake_connect(*args, **kwargs):
        return mock_ws

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_connect):
        await bridge.connect("luna")

    assert bridge._page_filter == "luna"
    bridge._reader_task.cancel()


async def test_reconnect_closes_and_reconnects():
    bridge = CDPBridge()
    bridge._page_filter = "luna"
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    close_called = []
    original_close = bridge.close

    async def fake_close():
        close_called.append(True)
        await original_close()

    async def fake_ws_connect(*args, **kwargs):
        return mock_ws

    bridge.close = fake_close

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_ws_connect), \
         patch("luna_mcp.cdp_bridge.asyncio.sleep", new_callable=AsyncMock):
        await bridge.reconnect()

    assert close_called
    assert bridge._ws is mock_ws
    bridge._reader_task.cancel()


async def test_reconnect_retries_with_backoff():
    bridge = CDPBridge()
    bridge._page_filter = None
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]
    mock_ws = AsyncMock()
    mock_ws.closed = False
    sleep_calls = []

    connect_attempts = [0]

    async def fake_connect(*args, **kwargs):
        connect_attempts[0] += 1
        if connect_attempts[0] < 2:
            raise ConnectionError("not ready")
        return mock_ws

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_connect), \
         patch("luna_mcp.cdp_bridge.asyncio.sleep", side_effect=fake_sleep):
        await bridge.reconnect()

    # Sleep only after failed attempt (before retry), not before first attempt
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 1.0
    bridge._reader_task.cancel()


async def test_reconnect_raises_after_max_retries():
    bridge = CDPBridge()
    bridge._page_filter = None

    async def fake_sleep(delay):
        pass

    with patch.object(bridge, "_discover_pages", side_effect=ConnectionError("down")), \
         patch("luna_mcp.cdp_bridge.asyncio.sleep", side_effect=fake_sleep):
        with pytest.raises(ConnectionError, match="retries"):
            await bridge.reconnect()


async def test_eval_auto_reconnects_on_connection_error():
    bridge = CDPBridge()
    bridge._ws = AsyncMock()
    bridge._ws.closed = False
    bridge._page_filter = None

    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    call_count = [0]
    loop = None

    async def fake_eval_impl(expression, timeout=30.0):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ConnectionError("ws closed")
        return "ok"

    reconnect_called = []

    async def fake_reconnect(page_filter=None):
        reconnect_called.append(True)

    bridge._eval_impl = fake_eval_impl
    bridge.reconnect = fake_reconnect

    result = await bridge.eval("1+1")
    assert result == "ok"
    assert reconnect_called


async def test_screenshot_auto_reconnects():
    bridge = CDPBridge()
    bridge._ws = AsyncMock()
    bridge._ws.closed = False
    bridge._page_filter = None

    call_count = [0]

    async def fake_screenshot_impl(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ConnectionError("ws closed")
        return b"\x89PNG"

    reconnect_called = []

    async def fake_reconnect(page_filter=None):
        reconnect_called.append(True)

    bridge._screenshot_impl = fake_screenshot_impl
    bridge.reconnect = fake_reconnect

    result = await bridge.screenshot()
    assert result == b"\x89PNG"
    assert reconnect_called


# ── Phase 18: Log domain ────────────────────────────────────────────────────

async def test_enable_log_sends_command(bridge_with_ws):
    bridge = bridge_with_ws
    loop = asyncio.get_running_loop()
    sent = []

    async def fake_send(msg):
        data = json.loads(msg)
        sent.append(data["method"])
        loop.call_soon(bridge._pending[data["id"]].set_result, {"id": data["id"], "result": {}})

    bridge._ws.send = fake_send
    await bridge.enable_log()
    assert "Log.enable" in sent


def test_log_entry_added_error_parsed():
    """Log.entryAdded error entries should appear in console messages."""
    bridge = CDPBridge()
    event = {
        "method": "Log.entryAdded",
        "params": {"entry": {
            "level": "error",
            "source": "network",
            "text": "Failed to load resource",
            "timestamp": 123456.0,
        }},
    }
    result = bridge._parse_console_event(event)
    assert result is not None
    assert result["level"] == "E"
    assert result["timestamp"] == 123456.0
    assert "[network]" in result["text"]
    assert "Failed to load resource" in result["text"]


def test_log_entry_added_warning_parsed():
    bridge = CDPBridge()
    event = {
        "method": "Log.entryAdded",
        "params": {"entry": {
            "level": "warning",
            "source": "security",
            "text": "CSP violation",
            "timestamp": 789.0,
        }},
    }
    result = bridge._parse_console_event(event)
    assert result is not None
    assert result["level"] == "W"
    assert "[security]" in result["text"]


def test_log_entry_added_info_parsed():
    bridge = CDPBridge()
    event = {
        "method": "Log.entryAdded",
        "params": {"entry": {
            "level": "verbose",
            "source": "log",
            "text": "some info",
            "timestamp": 1.0,
        }},
    }
    result = bridge._parse_console_event(event)
    assert result is not None
    assert result["level"] == "I"


async def test_read_loop_captures_log_entry():
    """Log.entryAdded events in read loop should be added to _console_messages."""
    bridge = CDPBridge()
    event = json.dumps({
        "method": "Log.entryAdded",
        "params": {"entry": {
            "level": "error",
            "source": "network",
            "text": "WebGL context lost",
            "timestamp": 999.0,
        }},
    })

    async def fake_iter():
        yield event

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    # Log.entryAdded should be in console messages (parsed directly in _read_loop)
    msgs = bridge.get_console_messages()
    assert any("WebGL context lost" in m["text"] for m in msgs)


async def test_on_reconnect_callback_called():
    bridge = CDPBridge()
    bridge._page_filter = None
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]
    mock_ws = AsyncMock()
    mock_ws.closed = False

    callback_called = []

    async def on_reconnect():
        callback_called.append(True)

    async def fake_ws_connect(*args, **kwargs):
        return mock_ws

    bridge._on_reconnect = on_reconnect

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_ws_connect), \
         patch("luna_mcp.cdp_bridge.asyncio.sleep", new_callable=AsyncMock):
        await bridge.reconnect()

    assert callback_called
    bridge._reader_task.cancel()


# ── Item A1: Hardened _read_loop + reconnect-lock ───────────────────────────

async def test_read_loop_survives_bad_json():
    """Non-JSON frame must NOT kill the reader; subsequent valid frames resolve futures."""
    bridge = CDPBridge()
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bridge._pending[1] = future

    async def fake_iter():
        yield "not json{"
        yield json.dumps({"id": 1, "result": {"ok": True}})

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert future.done()
    assert future.result() == {"id": 1, "result": {"ok": True}}


async def test_read_loop_survives_subscriber_exception():
    """Subscriber raising must not kill the reader; second event still queued."""
    bridge = CDPBridge()
    call_count = [0]

    original_dispatch = bridge._dispatch_to_bus

    def dispatch_raises_first(data):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("subscriber boom")
        original_dispatch(data)

    bridge._dispatch_to_bus = dispatch_raises_first

    async def fake_iter():
        yield json.dumps({"method": "Console.messageAdded", "params": {"message": {"text": "first", "level": "log", "timestamp": 0}}})
        yield json.dumps({"method": "Console.messageAdded", "params": {"message": {"text": "second", "level": "log", "timestamp": 1}}})

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    # Second event still landed in the queue
    assert not bridge._events.empty()


async def test_read_loop_finally_fails_pending_on_any_exit():
    """A non-ConnectionClosed top-level exception triggers finally: pending future gets ConnectionError."""
    bridge = CDPBridge()
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    bridge._pending[1] = future

    cancel_called = [False]
    original_cancel = bridge.bus.cancel_all

    def fake_cancel():
        cancel_called[0] = True
        original_cancel()

    bridge.bus.cancel_all = fake_cancel

    async def fake_iter():
        raise ValueError("unexpected error")
        yield  # make it a generator

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    await bridge._read_loop()
    assert future.done()
    assert isinstance(future.exception(), ConnectionError)
    assert cancel_called[0]


def test_connected_false_after_reader_dead():
    """connected must return False when _reader_dead is True, even if ws is open."""
    bridge = CDPBridge()
    ws = Mock()
    ws.state = 1  # OPEN
    bridge._ws = ws
    bridge._reader_dead = True
    assert bridge.connected is False


async def test_read_loop_logs_warning_on_unexpected_iterator_exception():
    """Outer except must log at warning level, not silently swallow."""
    bridge = CDPBridge()

    async def fake_iter():
        raise AttributeError("misbehaving ws")
        yield  # make it a generator

    ws = MagicMock()
    ws.__aiter__ = lambda self: fake_iter()
    bridge._ws = ws

    with patch("luna_mcp.cdp_bridge._log") as mock_log:
        await bridge._read_loop()

    mock_log.warning.assert_called_once()
    call_args = mock_log.warning.call_args[0]
    assert "AttributeError" in call_args[1]


async def test_reconnect_serialized_single_connect():
    """Concurrent reconnect() calls must result in exactly one websockets.connect call."""
    bridge = CDPBridge()
    bridge._page_filter = None
    pages = [{"type": "page", "title": "Luna", "url": "http://a",
              "webSocketDebuggerUrl": "ws://a"}]

    connect_count = [0]
    mock_ws = AsyncMock()
    mock_ws.state = 1  # OPEN

    async def fake_ws_connect(*args, **kwargs):
        connect_count[0] += 1
        return mock_ws

    with patch.object(bridge, "_discover_pages", return_value=pages), \
         patch("luna_mcp.cdp_bridge.websockets.connect", side_effect=fake_ws_connect), \
         patch("luna_mcp.cdp_bridge.asyncio.sleep", new_callable=AsyncMock):
        await asyncio.gather(bridge.reconnect(), bridge.reconnect())

    assert connect_count[0] == 1
    bridge._reader_task.cancel()
