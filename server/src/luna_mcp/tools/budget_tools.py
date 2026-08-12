"""Budget management tools exposed to MCP."""
import pathlib

from ..budget import PRESETS, BudgetTracker, ToolRouter
from ..budget.visual_router import analyze_visual as _visual_route
from . import maybe_expose


async def _set_budget_auto(
    tracker: "BudgetTracker | None" = None,
    router: "ToolRouter | None" = None,
    data_dir: pathlib.Path | None = None,
) -> str:
    """Internal: reload cap from history, apply to tracker, return status string."""
    from luna_mcp.config import data_dir as _cfg_data_dir

    from ..budget.autotune import compute_cap, estimate_p_success
    from ..budget.history import SessionHistory, get_project_key
    _data = data_dir or _cfg_data_dir()

    # Reuse history already attached to tracker, else open our own
    history = getattr(tracker, "_history", None)
    own_history = history is None
    if own_history:
        history = SessionHistory(_data / "history.db")

    key = get_project_key()
    rows = history.recent(key, limit=30)
    new_cap = compute_cap(rows)
    p_success = estimate_p_success(rows)

    if own_history:
        history.close()

    # Apply to live tracker (C2 + M3)
    if tracker is not None:
        tracker.cap = new_cap
        tracker.reset()
    if router is not None and hasattr(router, "_p_success"):
        router._p_success = p_success

    return f"auto: cap={new_cap} from {len(rows)} sessions, p_success={p_success:.2f}"


def register_budget_tools(mcp, tracker: BudgetTracker, router: ToolRouter, *, exposed: set = frozenset()):
    """Register budget tools. Returns {name: (fn, params)} for batch."""

    async def analyze_visual(question: str, hint: str = "") -> str:
        """Smart visual analysis: routes to cheapest tool that answers the question.
        geometry/position → getCanvasInfo, visibility → getObjectDetail,
        color → getMaterials, animation → getAnimatorState, UI → visualSummary.
        Saves ~92% tokens vs screenshot for most questions."""
        return await _visual_route(question, hint)
    maybe_expose(mcp, analyze_visual, exposed)

    async def set_budget(mode: str = "work") -> str:
        """Switch budget mode: warmup (5k), work (30k), deep_debug (100k), auto.
        Resets spent counter."""
        if mode == "auto":
            return await _set_budget_auto(tracker, router)
        cap = PRESETS.get(mode)
        if cap is None:
            return f"error: unknown mode '{mode}' — use warmup|work|deep_debug|auto"
        tracker.cap = cap
        tracker.reset()
        return f"budget set to {mode}: cap={cap} tokens, counter reset"
    maybe_expose(mcp, set_budget, exposed)

    async def get_budget_status() -> str:
        """Return current budget usage: tokens spent/cap, skip/downgrade counts."""
        return tracker.status()
    maybe_expose(mcp, get_budget_status, exposed)

    return {
        "analyze_visual": (analyze_visual, None),
        "set_budget": (set_budget, None),
        "get_budget_status": (get_budget_status, None),
    }
