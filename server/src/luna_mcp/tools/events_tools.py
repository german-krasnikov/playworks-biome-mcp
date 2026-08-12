"""Push-based event tools: watch, stream_until, get_events, set_event_filter."""
import asyncio
import re
import time
from typing import Callable

from luna_mcp.cdp_bridge import EventBus

from . import maybe_expose


def _format_events(items: list, kind: str) -> str:
    if not items:
        return f"[no {kind} events]"
    lines = []
    for e in items:
        seq = e.get("seq", "?")
        text = e.get("text", "")
        level = e.get("level", "")
        prefix = f"[{level}] " if level else ""
        lines.append(f"#{seq} {prefix}{text}")
    return "\n".join(lines)


def register_events_tools(mcp, get_bridge: Callable, exposed: set):
    """Register event bus tools. Returns {name: (fn, params)} for batch."""

    async def watch(kinds: str = "console,network", pattern: str = ".*",
                    timeout_ms: int = 2000, max_events: int = 1) -> str:
        """Block until pattern matches event from kinds, or timeout. Push-based."""
        bridge = get_bridge()
        if not bridge or not getattr(bridge, "bus", None):
            return "[DEGRADED:eventbus:not_initialized]"
        try:
            regex = re.compile(pattern[:200], re.IGNORECASE)
        except re.error as e:
            return f"[INVALID: bad pattern: {e}]"
        kind_set = {k.strip() for k in kinds.split(",") if k.strip() in EventBus.KINDS}
        if not kind_set:
            return f"[INVALID: kinds must be from {EventBus.KINDS}]"
        sub = bridge.bus.subscribe(kind_set, regex, max_events)
        try:
            matches = await asyncio.wait_for(asyncio.shield(sub.future), timeout=timeout_ms / 1000)
            return _format_events(matches, kinds)
        except asyncio.TimeoutError:
            partial = list(sub.matches)
            return f"[TIMEOUT after {timeout_ms}ms, {len(partial)} partial matches]\n" + _format_events(partial, kinds)
        finally:
            bridge.bus.unsubscribe(sub)

    maybe_expose(mcp, watch, exposed)

    async def stream_until(condition_js: str, timeout_ms: int = 5000, poll_ms: int = 100) -> str:
        """Server-side polling: await JS expression to become truthy."""
        bridge = get_bridge()
        if not bridge:
            return "[DEGRADED:no_bridge]"
        start = time.monotonic()
        deadline = start + timeout_ms / 1000
        while time.monotonic() < deadline:
            try:
                result = await bridge.eval(condition_js)
                if result and str(result).lower() not in ("false", "null", "undefined", "0", ""):
                    ms = int((time.monotonic() - start) * 1000)
                    return f"OK {ms}ms"
            except ConnectionError as e:
                return f"[DEGRADED:bridge:disconnected: {e}]"
            except Exception:
                pass
            await asyncio.sleep(poll_ms / 1000)
        return f"TIMEOUT after {timeout_ms}ms"

    maybe_expose(mcp, stream_until, exposed)

    async def get_events(kind: str = "console", count: int = 20, since_seq: int = -1) -> str:
        """Snapshot recent events from bus buffer."""
        bridge = get_bridge()
        if not bridge or not getattr(bridge, "bus", None):
            return "[DEGRADED:eventbus:not_initialized]"
        if kind not in EventBus.KINDS:
            return f"[INVALID: kind must be from {EventBus.KINDS}]"
        items = bridge.bus.snapshot(kind, count, since_seq)
        return _format_events(items, kind)

    maybe_expose(mcp, get_events, exposed)

    async def set_event_filter(kind: str = "console", drop_regex: str = "") -> str:
        """Set noise-drop filter per kind. Empty regex clears filter."""
        bridge = get_bridge()
        if not bridge or not getattr(bridge, "bus", None):
            return "[DEGRADED:eventbus:not_initialized]"
        if kind not in EventBus.KINDS:
            return "[INVALID: unknown kind]"
        if drop_regex:
            try:
                re.compile(drop_regex)
            except re.error as e:
                return f"[INVALID: bad regex: {e}]"
        bridge.bus.set_filter(kind, drop_regex or None)
        return f"OK filter set for {kind}: {drop_regex or '<cleared>'}"

    maybe_expose(mcp, set_event_filter, exposed)

    return {
        "watch": (watch, None),
        "stream_until": (stream_until, None),
        "get_events": (get_events, None),
        "set_event_filter": (set_event_filter, None),
    }
