"""S5.4 Jake task discovery tool — pure Python, no Chrome."""
from __future__ import annotations

from ..luna_config.jake_tasks import _FALLBACK_KEY, discover_tasks
from . import maybe_expose


def register_jake_tasks_tools(mcp, *, exposed: set = frozenset()):
    async def discover_jake_tasks(project_dir: str) -> str:
        """Discover available Jake build tasks via 'jake -T'."""
        tasks = discover_tasks(project_dir)
        if "error" in tasks:
            return f"error: {tasks['error']}"
        is_fallback = tasks.pop(_FALLBACK_KEY, None) == "1"
        prefix = "[DEGRADED:jake:not installed, using seed catalog]\n" if is_fallback else ""
        lines = [f"{name}  # {desc}" for name, desc in sorted(tasks.items())]
        return prefix + "\n".join(lines)

    maybe_expose(mcp, discover_jake_tasks, exposed, read_only=True)
    return {"discover_jake_tasks": (discover_jake_tasks, None)}
