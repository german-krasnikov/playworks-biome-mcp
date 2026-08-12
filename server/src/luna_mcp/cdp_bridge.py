from __future__ import annotations

import asyncio
import base64
import json
import logging
import os

import aiohttp
import websockets

from luna_mcp.event_bus import EventBus, Subscription  # noqa: F401 — re-exported for compat

_BACKOFF_DELAYS = [1.0, 3.0, 8.0]
_log = logging.getLogger(__name__)


class CDPBridge:
    def __init__(self, port: int = None):
        self._port = port or int(os.environ.get("LUNA_CDP_PORT", "9222"))
        self._ws = None
        self._reader_dead = False
        self._counter = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._events: asyncio.Queue = asyncio.Queue()
        self._reader_task = None
        self._lock = asyncio.Lock()
        self._reconnect_lock = asyncio.Lock()
        self._console_messages: list[dict] = []
        self._network_requests: list[dict] = []
        self._page_filter: str | None = None
        self._on_reconnect: callable | None = None
        self._on_frame_navigated: callable | None = None
        self._debugger_paused: dict | None = None
        self._scripts: dict[str, str] = {}  # url -> scriptId
        self.bus = EventBus()
        # Tracing state
        self._trace_chunks: list = []
        self._tracing_active: bool = False
        self._trace_done: asyncio.Event = asyncio.Event()
        self._trace_overflow: bool = False

    @property
    def connected(self) -> bool:
        if self._ws is None or self._reader_dead:
            return False
        # websockets 13+: use .state (1=OPEN), older: use .closed
        if hasattr(self._ws, "state"):
            return self._ws.state == 1
        return not self._ws.closed

    def _find_page(self, pages: list[dict], filter_str: str = None) -> dict | None:
        for p in pages:
            if p.get("type") != "page":
                continue
            url = p.get("url", "")
            if url.startswith("devtools://") or url.startswith("chrome://"):
                continue
            if filter_str and filter_str.lower() not in (p.get("title", "") + url).lower():
                continue
            return p
        return None

    async def connect(self, page_filter: str = None):
        self._page_filter = page_filter
        self._reader_dead = False
        pages = await self._discover_pages()
        page = self._find_page(pages, page_filter)
        if not page:
            raise ConnectionError("No debuggable page found")
        self._ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=10_000_000)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def reconnect(self, page_filter: str = None) -> None:
        """Reconnect with exponential backoff. Reuses saved page_filter if not given."""
        async with self._reconnect_lock:
            if self.connected:
                return
            await self.close()
            pf = page_filter if page_filter is not None else self._page_filter
            for i, delay in enumerate(_BACKOFF_DELAYS):
                try:
                    await self.connect(pf)
                    if self._on_reconnect:
                        await self._on_reconnect()
                    return
                except (ConnectionError, OSError, aiohttp.ClientError):
                    if i == len(_BACKOFF_DELAYS) - 1:
                        raise ConnectionError(f"Failed to reconnect after {len(_BACKOFF_DELAYS)} retries")
                    await asyncio.sleep(delay)

    async def eval(self, expression: str, timeout: float = 30.0) -> str:
        try:
            return await self._eval_impl(expression, timeout)
        except (ConnectionError, websockets.ConnectionClosed):
            await self.reconnect()
            return await self._eval_impl(expression, timeout)

    async def _eval_impl(self, expression: str, timeout: float = 30.0) -> str:
        result = await self.send_cdp("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        }, timeout)
        if "error" in result:
            raise RuntimeError(result["error"].get("message", "CDP error"))
        inner = result.get("result", {})
        if "exceptionDetails" in inner:
            raise RuntimeError(inner["exceptionDetails"].get("text", "JS error"))
        val = inner.get("result", {})
        if val.get("type") == "undefined":
            return ""
        return str(val.get("value", ""))

    async def enable_all_domains(self) -> None:
        """Enable Console + Runtime + Network + Log (best-effort) domains."""
        await self.enable_console()
        await self.enable_network()
        try:
            await self.enable_log()
        except Exception:
            pass

    async def enable_network(self) -> None:
        await self.send_cdp("Network.enable")

    def get_network_requests(self, count: int = 50, filter_str: str = "") -> list[dict]:
        result = self._network_requests
        if filter_str:
            result = [r for r in result if filter_str.lower() in r.get("url", "").lower()]
        return result[-count:]

    def _parse_network_event(self, event: dict) -> dict | None:
        method = event.get("method", "")
        params = event.get("params", {})
        if method == "Network.requestWillBeSent":
            req = params.get("request", {})
            return {"id": params.get("requestId"), "url": req.get("url", ""),
                    "method": req.get("method", ""), "status": "pending", "type": params.get("type", "")}
        if method == "Network.responseReceived":
            resp = params.get("response", {})
            rid = params.get("requestId")
            for r in reversed(self._network_requests):
                if r.get("id") == rid:
                    r["status"] = resp.get("status", 0)
                    r["mime"] = resp.get("mimeType", "")
                    return None
        if method == "Network.loadingFailed":
            rid = params.get("requestId")
            for r in reversed(self._network_requests):
                if r.get("id") == rid:
                    r["status"] = "FAIL"
                    r["error"] = params.get("errorText", "")
                    return None
        return None

    async def enable_console(self) -> None:
        """Enable Console + Runtime domains to capture console output."""
        await self.send_cdp("Console.enable")
        await self.send_cdp("Runtime.enable")

    async def enable_log(self) -> None:
        """Enable Log domain to catch WebGL/network/CSP errors."""
        await self.send_cdp("Log.enable")

    def get_console_messages(self, count: int = 50, level: str = "") -> list[dict]:
        """Drain events queue, return filtered/limited messages."""
        while not self._events.empty():
            try:
                event = self._events.get_nowait()
                msg = self._parse_console_event(event)
                if msg:
                    self._console_messages.append(msg)
            except asyncio.QueueEmpty:
                break
        if len(self._console_messages) >= 500:
            self._console_messages = self._console_messages[-500:]
        result = self._console_messages
        if level:
            result = [m for m in result if m["level"] == level.upper()[0]]
        return result[-count:]

    def _parse_console_event(self, event: dict) -> dict | None:
        """Parse Console.messageAdded or Runtime.consoleAPICalled into dict."""
        method = event.get("method", "")
        params = event.get("params", {})
        if method == "Console.messageAdded":
            msg = params.get("message", {})
            level = {"error": "E", "warning": "W"}.get(msg.get("level", ""), "I")
            return {"level": level, "timestamp": msg.get("timestamp", 0), "text": msg.get("text", "")}
        if method == "Runtime.consoleAPICalled":
            level = {"error": "E", "warning": "W", "warn": "W"}.get(params.get("type", ""), "I")
            args = params.get("args", [])
            text = " ".join(str(a.get("value", a.get("description", ""))) for a in args)
            return {"level": level, "timestamp": params.get("timestamp", 0), "text": text}
        if method == "Log.entryAdded":
            entry = params.get("entry", {})
            level = {"error": "E", "warning": "W"}.get(entry.get("level", ""), "I")
            return {"level": level, "timestamp": entry.get("timestamp", 0),
                    "text": f"[{entry.get('source', 'log')}] {entry.get('text', '')}"}
        return None

    async def screenshot(self, *, format: str = "png", quality: int = 0,
                         clip: dict | None = None, max_width: int = 0) -> bytes:
        try:
            return await self._screenshot_impl(format=format, quality=quality,
                                               clip=clip, max_width=max_width)
        except (ConnectionError, websockets.ConnectionClosed):
            await self.reconnect()
            return await self._screenshot_impl(format=format, quality=quality,
                                               clip=clip, max_width=max_width)

    async def _screenshot_impl(self, *, format: str = "png", quality: int = 0,
                                clip: dict | None = None, max_width: int = 0) -> bytes:
        params: dict = {"format": format}
        if format == "jpeg" and quality:
            params["quality"] = quality
        if clip:
            params["clip"] = clip
        result = await self.send_cdp("Page.captureScreenshot", params)
        raw = base64.b64decode(result["result"]["data"])
        if max_width > 0:
            try:
                import io

                from PIL import Image
                img = Image.open(io.BytesIO(raw))
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_h = max(1, round(img.height * ratio))
                    img = img.resize((max_width, new_h), Image.LANCZOS)
                    buf = io.BytesIO()
                    save_fmt = "JPEG" if format == "jpeg" else "PNG"
                    if save_fmt == "JPEG":
                        img = img.convert("RGB")
                        img.save(buf, format="JPEG", quality=quality or 85)
                    else:
                        img.save(buf, format="PNG")
                    return buf.getvalue()
            except ImportError:
                pass
        return raw

    async def send_cdp(self, method: str, params: dict = None, timeout: float = 30.0) -> dict:
        if self._ws is None:
            raise ConnectionError("Not connected")
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        async with self._lock:
            self._counter += 1
            msg_id = self._counter
            self._pending[msg_id] = future
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        await self._ws.send(json.dumps(msg))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(msg_id, None)

    def _dispatch_to_bus(self, data: dict) -> None:
        """Publish CDP event to EventBus (sync, non-blocking)."""
        method = data.get("method", "")
        params = data.get("params", {})
        if method in ("Runtime.consoleAPICalled", "Console.messageAdded", "Log.entryAdded"):
            msg = self._parse_console_event(data)
            if msg:
                self.bus.publish("console", dict(msg))
        elif method in ("Network.requestWillBeSent",):
            req = params.get("request", {})
            self.bus.publish("network", {"text": req.get("url", ""), "method": req.get("method", "")})
        elif method == "Runtime.exceptionThrown":
            exc = params.get("exceptionDetails", {})
            text = exc.get("text", "") or str(exc.get("exception", {}).get("description", ""))
            self.bus.publish("exception", {"text": text})
        elif method == "Page.frameNavigated":
            frame = params.get("frame", {})
            self.bus.publish("frame", {"text": frame.get("url", ""), "id": frame.get("id", "")})

    def _handle_event(self, data: dict) -> None:
        """Process a CDP event (method-based). Called from _read_loop and tests."""
        method = data.get("method", "")
        if method == "Tracing.dataCollected" and self._tracing_active:
            if len(self._trace_chunks) <= 200_000:
                self._trace_chunks.extend(data.get("params", {}).get("value", []))
                if len(self._trace_chunks) > 200_000:
                    self._trace_overflow = True
            return
        if method == "Tracing.tracingComplete":
            self._tracing_active = False
            self._trace_done.set()
            return
        if method == "Debugger.paused":
            self._debugger_paused = data.get("params", {})
        elif method == "Debugger.resumed":
            self._debugger_paused = None
        elif method == "Page.frameNavigated":
            if self._on_frame_navigated:
                asyncio.create_task(self._on_frame_navigated())
        elif method == "Debugger.scriptParsed":
            params = data.get("params", {})
            url = params.get("url", "")
            script_id = params.get("scriptId", "")
            if url:
                self._scripts[url] = script_id
        net = self._parse_network_event(data)
        if net:
            self._network_requests.append(net)
            if len(self._network_requests) > 200:
                self._network_requests = self._network_requests[-200:]
        self._dispatch_to_bus(data)
        self._events.put_nowait(data)

    def start_trace_collection(self) -> None:
        """Prepare bridge to collect Tracing.dataCollected events."""
        self._trace_chunks = []
        self._trace_overflow = False
        self._trace_done.clear()
        self._tracing_active = True

    async def wait_trace_complete(self, timeout: float = 10.0) -> None:
        """Wait until Tracing.tracingComplete event arrives."""
        await asyncio.wait_for(self._trace_done.wait(), timeout)

    def take_trace_chunks(self) -> list:
        """Return collected trace chunks and clear internal buffer."""
        chunks = self._trace_chunks
        self._trace_chunks = []
        return chunks

    async def _read_loop(self):
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                    msg_id = data.get("id")
                    if msg_id is not None and msg_id in self._pending:
                        self._pending[msg_id].set_result(data)
                    else:
                        self._handle_event(data)
                except Exception as exc:
                    _log.warning("_read_loop: bad frame skipped: %s", exc)
        except Exception as exc:
            _log.warning("_read_loop: iterator exited with %s: %s", type(exc).__name__, exc)
        finally:
            self._reader_dead = True
            self.bus.cancel_all()
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("WebSocket closed"))

    async def discover_pages(self, port: int = 0) -> list[dict]:
        """Public wrapper for page discovery (HTTP only, no WebSocket needed)."""
        return await self._discover_pages(port=port)

    async def _discover_pages(self, port: int = 0) -> list[dict]:
        target = port if port > 0 else self._port
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{target}/json") as resp:
                return await resp.json()

    async def close(self):
        self.bus.cancel_all()
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
