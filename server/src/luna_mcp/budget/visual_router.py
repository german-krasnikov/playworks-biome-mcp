"""Smart visual router: picks cheapest path for visual questions."""
from typing import Awaitable, Callable

# Injected at wiring time by server.py or tests
_call_fn: Callable[..., Awaitable[str]] | None = None


async def _call(method: str, *args) -> str:
    if _call_fn is None:
        raise RuntimeError("visual_router._call_fn not wired")
    return await _call_fn(method, *args)


async def analyze_visual(question: str, hint: str = "") -> str:
    """Smart visual analysis. Picks cheapest path that answers the question.

    Args:
        question: free-text question. Keywords trigger routing:
            - "position", "anchor", "rect", "size" → getCanvasInfo
            - "active", "enabled", "visible" → getObjectDetail
            - "color", "material", "shader" → getMaterials
            - "animator", "state", "animation" → getAnimatorState
            - "ui", "button", "label" → visualSummary(ui_only)
            - else → visualSummary(compact)
        hint: optional path/name to focus on. Empty string (default) = scene root.

    Returns: text result from delegated tool, ≤200 tokens for cheapest paths.
    """
    q = question.lower()
    target = hint or ""

    if any(k in q for k in ("position", "anchor", "rect", "size")):
        return await _call("getCanvasInfo", target)
    if any(k in q for k in ("active", "enabled", "visible")):
        return await _call("getObjectDetail", target)
    if any(k in q for k in ("color", "material", "shader")):
        return await _call("getMaterials", target)
    if any(k in q for k in ("animator", "state", "animation")):
        return await _call("getAnimatorState", target)
    if any(k in q for k in ("ui", "button", "label")):
        return await _call("visualSummary", "ui_only")
    return await _call("visualSummary", "compact")
