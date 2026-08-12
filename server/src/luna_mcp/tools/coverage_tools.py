"""S4.1 Coverage profiler tools."""
import asyncio

from ..coverage_map import map_dead_functions
from . import maybe_expose


def register_coverage_tools(mcp, get_bridge, require_source_mapper, *, exposed: set = frozenset()):
    async def coverage_report(duration_ms: int = 3000, top: int = 30) -> str:
        """Profiler coverage report: maps dead JS ranges to C# methods."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        coverage_result = []
        try:
            await bridge.send_cdp("Profiler.enable")
            await bridge.send_cdp("Profiler.startPreciseCoverage", {
                "callCount": False,
                "detailed": True,
            })
            if duration_ms > 0:
                await asyncio.sleep(duration_ms / 1000)
            try:
                result = await bridge.send_cdp("Profiler.takePreciseCoverage")
                coverage_result = result.get("result", {}).get("result", [])
            except Exception as e:
                return f"[DEGRADED] {e}"
            finally:
                try:
                    await bridge.send_cdp("Profiler.stopPreciseCoverage")
                except Exception:
                    pass
        except Exception as e:
            return f"[DEGRADED] {e}"
        finally:
            try:
                await bridge.send_cdp("Profiler.disable")
            except Exception:
                pass
        if not coverage_result:
            return "[DEGRADED] empty coverage result"
        mapped = await map_dead_functions(coverage_result, require_source_mapper, top=top)
        return mapped[:4000]

    maybe_expose(mcp, coverage_report, exposed, read_only=True)

    async def coverage_raw(duration_ms: int = 0) -> str:
        """Raw coverage counts: scripts + unexecuted range count."""
        bridge = get_bridge()
        if bridge is None:
            return "[DEGRADED] not connected"
        try:
            await bridge.send_cdp("Profiler.enable")
            await bridge.send_cdp("Profiler.startPreciseCoverage", {
                "callCount": False,
                "detailed": True,
            })
            if duration_ms > 0:
                await asyncio.sleep(duration_ms / 1000)
            try:
                result = await bridge.send_cdp("Profiler.takePreciseCoverage")
                scripts = result.get("result", {}).get("result", [])
            except Exception as e:
                return f"[DEGRADED] {e}"
            finally:
                try:
                    await bridge.send_cdp("Profiler.stopPreciseCoverage")
                except Exception:
                    pass
        except Exception as e:
            return f"[DEGRADED] {e}"
        finally:
            try:
                await bridge.send_cdp("Profiler.disable")
            except Exception:
                pass
        total_fns = sum(len(s.get("functions", [])) for s in scripts)
        dead_fns = sum(
            1 for s in scripts for fn in s.get("functions", [])
            if fn.get("ranges") and all(r.get("count", 1) == 0 for r in fn["ranges"])
        )
        return f"scripts: {len(scripts)}  functions: {total_fns}  dead: {dead_fns}"

    maybe_expose(mcp, coverage_raw, exposed, read_only=True)

    return {
        "coverage_report": (coverage_report, None),
        "coverage_raw": (coverage_raw, None),
    }
