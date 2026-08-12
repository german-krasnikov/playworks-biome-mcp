"""MCP tool: distill_hierarchy (F16 Hierarchy Distiller)."""
from __future__ import annotations

from ..hierarchy_distiller.distiller import distill
from ..tools import maybe_expose

# Module-level sampling reference — wired by server.py (or None for tests)
_sampling = None


async def distill_hierarchy(hierarchy: str, threshold: int = 50) -> str:
    """Distill a large hierarchy into stats. Returns raw if below threshold."""
    return await distill(hierarchy, threshold, _sampling)


def register_distiller_tools(mcp, exposed: set[str]) -> dict:
    maybe_expose(mcp, distill_hierarchy, exposed, name="distill_hierarchy", read_only=True)
    return {"distill_hierarchy": (distill_hierarchy, None)}
