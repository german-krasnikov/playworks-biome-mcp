"""S4.4 HeapProfiler sampling tool."""
import asyncio

from ..heap_summary import summarize
from . import maybe_expose


def register_heap_tools(mcp, get_bridge, *, exposed: set = frozenset()):
    async def heap_sample(duration_ms: int = 5000, top: int = 15) -> str:
        """Sample JS heap allocations. duration_ms=0 for instant snapshot."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        profile = {}
        try:
            await bridge.send_cdp("HeapProfiler.enable")
            await bridge.send_cdp("HeapProfiler.startSampling", {"samplingInterval": 32768})
            if duration_ms > 0:
                await asyncio.sleep(duration_ms / 1000)
            try:
                result = await bridge.send_cdp("HeapProfiler.stopSampling")
                profile = result.get("result", {}).get("profile", {})
            except Exception as e:
                return f"[DEGRADED] {e}"
        except Exception as e:
            return f"[DEGRADED] {e}"
        finally:
            try:
                await bridge.send_cdp("HeapProfiler.disable")
            except Exception:
                pass
        return summarize(profile, top)

    maybe_expose(mcp, heap_sample, exposed, read_only=True)

    return {"heap_sample": (heap_sample, None)}
