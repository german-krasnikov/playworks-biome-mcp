import asyncio
import json
import os
import tempfile
import time

from mcp.server.fastmcp.exceptions import ToolError

from . import maybe_expose

_CONSOLE_MSG_CAP = 200


def _cap(text: str) -> str:
    if len(text) > _CONSOLE_MSG_CAP:
        return f"{text[:_CONSOLE_MSG_CAP]}… (+{len(text) - _CONSOLE_MSG_CAP} chars)"
    return text


def register_diagnostics_tools(mcp, send_fn, call_fn, bridge_getter, ensure_fn=None, *, exposed: set = frozenset()):
    """Register diagnostics/utility tools. Returns {name: (fn, params)} for batch."""

    async def eval_js(expression: str, timeout: float = 30.0) -> str:
        """Execute arbitrary JS in the Luna page context and return the string result. Use for one-off queries or when no dedicated tool exists. All other tools are built on top of this."""
        return await send_fn(expression, timeout=timeout)
    maybe_expose(mcp, eval_js, exposed)

    async def screenshot() -> str:
        """Capture a full-page screenshot, saved to /tmp. Returns the file path. Use to visually verify scene state, UI layout, or collider overlays."""
        from ..config import SCREENSHOT_FORMAT, SCREENSHOT_MAX_WIDTH, SCREENSHOT_QUALITY
        if ensure_fn:
            await ensure_fn()
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        try:
            data = await bridge.screenshot(format=SCREENSHOT_FORMAT, quality=SCREENSHOT_QUALITY,
                                           max_width=SCREENSHOT_MAX_WIDTH)
        except Exception as e:
            raise ToolError(f"Screenshot failed: {e}")
        ext = ".jpg" if SCREENSHOT_FORMAT == "jpeg" else ".png"
        path = os.path.join(tempfile.gettempdir(), f"luna_screenshot{ext}")
        with open(path, "wb") as f:
            f.write(data)
        return f"Screenshot saved to: {path}"
    maybe_expose(mcp, screenshot, exposed)

    async def get_console(count: int = 50, level: str = "", since: int = -1) -> str:
        """Read recent console messages from the Luna page. level: E(rror), W(arning), I(nfo) or empty for all.
        since: index offset for incremental reading (pass last count to get only new messages). -1 returns all up to count."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        if ensure_fn:
            await ensure_fn()
        msgs = bridge.get_console_messages(count, level)
        if since >= 0 and since < len(msgs):
            msgs = msgs[since:]
        if not msgs:
            return "(no console messages)"
        lines = []
        for m in msgs:
            ts = m["timestamp"]
            if ts > 1e12:
                ts = ts / 1000
            t = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "??:??:??"
            lines.append(f"[{m['level']} {t}] {_cap(m['text'])}")
        return "\n".join(lines)
    maybe_expose(mcp, get_console, exposed)

    async def get_connection_info() -> str:
        """Connection status: port, page, helpers version, debugger presence."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        lines = [f"port: {bridge._port}", f"connected: {bridge.connected}"]
        if bridge.connected:
            async def _try(expr, fallback):
                try: return await bridge.eval(expr)
                except Exception: return fallback
            url = await _try("window.location.href", "(error reading)")
            title = await _try("document.title", "")
            lines += [f"page_url: {url}", f"page_title: {title}"]
            ver = await _try("document.querySelector('iframe')?.contentWindow?.__luna_mcp?.version || 'not injected'", "unknown")
            lines.append(f"helpers: {ver}")
            dbg = await _try("typeof pc !== 'undefined' && pc.Debugger ? 'available' : 'not found'", "unknown")
            lines.append(f"debugger: {dbg}")
        return "\n".join(lines)
    maybe_expose(mcp, get_connection_info, exposed)

    async def list_pages(port: int = 0) -> str:
        """List all debuggable Chrome pages. port=0 uses current."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        try:
            pages = await bridge.discover_pages(port=port)
        except Exception as e:
            raise ToolError(f"Cannot reach Chrome: {e}")
        if not pages:
            return "(no pages found)"
        lines = [f"[{p.get('type', '?')}] {p.get('title', 'untitled')} - {p.get('url', '')}" for p in pages]
        return "\n".join(lines)
    maybe_expose(mcp, list_pages, exposed)

    async def discover_custom_components() -> str:
        """List custom components not registered in Luna Debugger."""
        return await call_fn("discoverCustomComponents")
    maybe_expose(mcp, discover_custom_components, exposed)

    async def register_custom_components() -> str:
        """Auto-register custom components in Luna Debugger for inspection."""
        return await call_fn("registerCustomComponents")
    maybe_expose(mcp, register_custom_components, exposed)

    async def get_build_environment() -> str:
        """Runtime build config: SDK version, platform, target, encoding. Reads window.$environment."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        raw = await send_fn(
            "(() => {"
            "  const e = document.querySelector('iframe')?.contentWindow?.$environment;"
            "  if (!e) return '{}';"
            "  const r = {};"
            "  for (const [k,v] of Object.entries(e)) { if (typeof v !== 'object') r[k] = v; }"
            "  const pc = e.packageConfig || {};"
            "  for (const [k,v] of Object.entries(pc)) { if (typeof v !== 'object') r['pkg.'+k] = v; }"
            "  const rc = e.resourceConfig || {};"
            "  r['resources'] = Object.entries(rc).map(([k,v]) => k+'='+v).join(', ');"
            "  return JSON.stringify(r);"
            "})()"
        )
        if not raw or raw in ("{}", "undefined"):
            return "(no $environment found)"
        try:
            env = json.loads(raw)
        except Exception:
            return f"(parse error: {raw[:200]})"
        lines = ["BUILD ENVIRONMENT:"]
        for k, v in env.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    async def get_startup_timing() -> str:
        """Startup performance breakdown from Luna's built-in timing (lunaStartup)."""
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        raw = await send_fn(
            "(() => {"
            "  const w = document.querySelector('iframe')?.contentWindow;"
            "  if (!w || !w.lunaStartup) return '{}';"
            "  const s = w.lunaStartup;"
            "  const ts = s.timestamps || {};"
            "  const mt = s.measuredTime || {};"
            "  return JSON.stringify({timestamps: ts, measured: mt});"
            "})()"
        )
        if not raw or raw in ("{}", "undefined"):
            return "(no startup timing found)"
        try:
            data = json.loads(raw)
        except Exception:
            return f"(parse error: {raw[:200]})"
        lines = ["STARTUP TIMING:"]
        for k, v in (data.get("timestamps") or {}).items():
            lines.append(f"  {k}: {v}ms")
        for k, v in (data.get("measured") or {}).items():
            lines.append(f"  {k}: {v}ms")
        return "\n".join(lines)
    maybe_expose(mcp, get_startup_timing, exposed)

    async def luna_report(report: str = "debug") -> str:
        """Run Luna's built-in reports. report: startup|shader|debug.
        Calls Luna.StartupReport(), Luna.ShaderReport(), or Luna.LogDebugInfo()."""
        valid = {
            "startup": "Luna.StartupReport()",
            "shader": "Luna.ShaderReport()",
            "debug": "Luna.LogDebugInfo()",
        }
        if report not in valid:
            return f"unknown report '{report}', use: {', '.join(valid)}"
        bridge = bridge_getter()
        if bridge is None:
            raise ToolError("Server not initialized")
        pre_count = len(bridge.get_console_messages(500))
        try:
            await send_fn(
                f"document.querySelector('iframe')?.contentWindow?.{valid[report]}"
            )
        except Exception:
            return f"({valid[report]} not available)"
        await asyncio.sleep(0.15)
        msgs = bridge.get_console_messages(500)
        new_msgs = msgs[pre_count:]
        if not new_msgs:
            return f"(no output from {valid[report]})"
        return "\n".join(m["text"][:200] for m in new_msgs)

    return {
        "eval_js": (eval_js, None),
        "screenshot": (screenshot, None),
        "get_console": (get_console, None),
        "get_connection_info": (get_connection_info, None),
        "list_pages": (list_pages, None),
        "discover_custom_components": (discover_custom_components, None),
        "register_custom_components": (register_custom_components, None),
        "get_build_environment": (get_build_environment, None),
        "get_startup_timing": (get_startup_timing, None),
        "luna_report": (luna_report, None),
    }
