"""Physics Detective MCP tools: detect, diagnose, health check, compare states."""
from typing import Callable, Optional

from . import maybe_expose

# Module-level singletons — set by server.py lifespan
_diagnostic = None
_compare_states_fn: Optional[Callable] = None


async def compare_physics_states(label_a: str, label_b: str) -> str:
    """Compare two physics states via animation timeline diff."""
    if _compare_states_fn is None:
        return "[DEGRADED:physics:compare_states unavailable]"
    return await _compare_states_fn(label_a, label_b)


def register_physics_tools(mcp, call_fn, sampling, store, *, exposed: set = frozenset()):
    """Register physics tools. call_fn/sampling/store may be None (initialized later via lifespan)."""

    async def detect_physics_backend() -> str:
        """Detect active physics backend (Goblin/Verlet/Baked/Unified) via JS probe."""
        if _diagnostic is None:
            return "[DEGRADED:physics:not_initialized]"
        return await _diagnostic.detect()
    maybe_expose(mcp, detect_physics_backend, exposed)

    async def diagnose_physics(symptom: str, deep: bool = False) -> str:
        """Diagnose a physics symptom: detect backend → classify → query lessons."""
        if _diagnostic is None:
            return "[DEGRADED:physics:not_initialized]"
        return await _diagnostic.diagnose(symptom, deep)
    maybe_expose(mcp, diagnose_physics, exposed)

    async def physics_health_check() -> str:
        """Check physics backend health: active backends + perf warnings."""
        if _diagnostic is None:
            return "[DEGRADED:physics:not_initialized]"
        return await _diagnostic.health_check()
    maybe_expose(mcp, physics_health_check, exposed)

    maybe_expose(mcp, compare_physics_states, exposed)

    return {
        "detect_physics_backend": (detect_physics_backend, None),
        "diagnose_physics": (diagnose_physics, None),
        "physics_health_check": (physics_health_check, None),
        "compare_physics_states": (compare_physics_states, None),
    }
