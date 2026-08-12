"""2 MCP tools for Build Optimization Macro (F10)."""
from __future__ import annotations

from typing import Optional

from ..optimize_macro.orchestrator import BuildOptimizer
from ..tools import maybe_expose

_orchestrator: Optional[BuildOptimizer] = None


async def optimize_build_size(target_kb: int = 500, asset_path: str = "") -> str:
    """Produce a unified build-size reduction plan targeting target_kb. Orchestrates three analyzers: Jakefile (script bundling), PC modules (dead-code elimination), and asset compression. Returns a prioritized list of actions. Use optimize_status first if the result looks incomplete."""
    if _orchestrator is None:
        return "[DEGRADED:optimize:not_initialized]"
    if target_kb < 1:
        return "[INVALID: target_kb must be >= 1]"
    if target_kb > 50000:
        return "[INVALID: target_kb too large (max 50000)]"
    plan = await _orchestrator.optimize(target_kb, asset_path)
    return plan.to_text()


async def optimize_status() -> str:
    """Check which optimization subsystems are available (Jakefile/PC modules/assets). Run this when optimize_build_size returns an incomplete plan or you suspect a subsystem is missing."""
    if _orchestrator is None:
        return "[DEGRADED:optimize:not_initialized]"
    parts = ["optimize_build_size subsystems:"]
    parts.append(f"  jakefile (F4): {'available' if _orchestrator.has_jakefile else 'unavailable'}")
    parts.append(f"  pc_modules (F5): {'available' if _orchestrator.has_pc else 'unavailable'}")
    parts.append(f"  assets (F6): {'available' if _orchestrator.has_assets else 'unavailable'}")
    return "\n".join(parts)


def register_optimize_tools(
    mcp,
    orchestrator: Optional[BuildOptimizer] = None,
    *,
    exposed: set = frozenset(),
) -> dict:
    global _orchestrator
    if orchestrator is not None:
        _orchestrator = orchestrator

    maybe_expose(mcp, optimize_build_size, exposed, name="optimize_build_size")
    maybe_expose(mcp, optimize_status, exposed, name="optimize_status")

    return {
        "optimize_build_size": (optimize_build_size, None),
        "optimize_status":     (optimize_status,      None),
    }
