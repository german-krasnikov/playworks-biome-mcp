"""S4.3 Tracing tool — frame timing profiler via CDP Tracing domain."""
import asyncio

from ..trace_summary import summarize
from . import maybe_expose

_CATEGORIES = "disabled-by-default-devtools.timeline,blink.user_timing,toplevel"


def register_trace_tools(mcp, get_bridge, *, exposed: set = frozenset()):
    async def trace_frames(duration_ms: int = 3000) -> str:
        """Trace JS frame timing. Returns avg/p95 fps, jank count, long tasks."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        try:
            bridge.start_trace_collection()
            await bridge.send_cdp("Tracing.start", {
                "categories": _CATEGORIES,
                "transferMode": "ReportEvents",
            })
            if duration_ms > 0:
                await asyncio.sleep(duration_ms / 1000)
            await bridge.send_cdp("Tracing.end")
            try:
                await bridge.wait_trace_complete(timeout=10)
            except asyncio.TimeoutError:
                return "[DEGRADED] trace did not complete"
            chunks = bridge.take_trace_chunks()
            overflow = getattr(bridge, "_trace_overflow", False)
            return summarize(chunks, overflow=overflow)
        except Exception as e:
            return f"[DEGRADED] {e}"
        finally:
            bridge._tracing_active = False

    maybe_expose(mcp, trace_frames, exposed, read_only=True)

    return {"trace_frames": (trace_frames, None)}
