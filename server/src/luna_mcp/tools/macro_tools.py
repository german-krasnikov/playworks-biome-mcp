"""Macro tools: high-level intent → plan → validate → execute."""
from typing import Callable, Optional

from luna_mcp.macro.planner import plan_batch
from luna_mcp.macro.whitelist import READ_ONLY_TOOLS

from . import maybe_expose


def _degraded() -> str:
    return "[DEGRADED:macro:disabled — set LUNA_VISUAL_LLM=1 + install claude CLI]"


async def _run_kind(
    intent: str,
    kind: str,
    get_sampling,
    get_tool_registry,
    execute_batch_fn,
) -> str:
    sampling = get_sampling()
    if sampling is None or not sampling.enabled:
        return _degraded()
    plan = await plan_batch(intent, kind, sampling, get_tool_registry())
    if not plan:
        return "[PLANNER_UNAVAILABLE: empty plan]"
    dry = await execute_batch_fn(plan, dry_run=True)
    if "[BATCH ABORTED" in dry or "[INVALID:" in dry:
        return f"PLAN_INVALID:\n{plan}\n---\n{dry}"
    result = await execute_batch_fn(plan)
    return f"PLAN:\n{plan}\n\nRESULT:\n{result}"


def register_macro_tools(
    mcp,
    get_sampling: Callable,
    get_tool_registry: Callable,
    exposed: set,
    execute_batch_fn: Optional[Callable] = None,
) -> dict:
    """Register do/ask/endcard/gameplay/monetization macro tools."""
    if execute_batch_fn is None:
        from luna_mcp.tools.batch import execute_batch
        execute_batch_fn = execute_batch

    async def do(intent: str) -> str:
        """General-purpose mutation macro for a Luna playable ad scene. Haiku generates a batch DSL plan, validates it with dry_run, then executes. Use when you need to inspect AND mutate (e.g. 'make the CTA button red'). Prefer over route_intent when the task needs multi-step discovery→inspect→mutate. For read-only queries use ask. For scoped work use endcard/gameplay/monetization."""
        return await _run_kind(intent, "do", get_sampling, get_tool_registry, execute_batch_fn)
    maybe_expose(mcp, do, exposed)

    async def ask(question: str) -> str:
        """Read-only scene query macro. Haiku plans a batch DSL script, then rejects it if any mutation tool appears. Use for questions like 'what is the CTA button color?' or 'are there console errors?'. Safer than do — guaranteed no side effects."""
        sampling = get_sampling()
        if sampling is None or not sampling.enabled:
            return "[DEGRADED:macro:disabled]"
        plan = await plan_batch(question, "ask", sampling, get_tool_registry())
        if not plan:
            return "[PLANNER_UNAVAILABLE: empty plan]"
        for line in plan.split("\n"):
            cmd = line.split()[0] if line.strip() else ""
            if cmd and cmd not in READ_ONLY_TOOLS:
                return (
                    f"ASK_MUTATION_REJECTED: line '{line}' uses non-read-only tool {cmd}"
                    f"\nPLAN:\n{plan}"
                )
        dry = await execute_batch_fn(plan, dry_run=True)
        if "[BATCH ABORTED" in dry or "[INVALID:" in dry:
            return f"PLAN_INVALID:\n{plan}\n---\n{dry}"
        result = await execute_batch_fn(plan)
        return f"PLAN:\n{plan}\n\nRESULT:\n{result}"
    maybe_expose(mcp, ask, exposed)

    async def endcard(intent: str) -> str:
        """Macro scoped to the endcard — the final screen of a playable ad (objects matching EndCard/Install/CTA/Final). Use for tasks like 'trigger the install button' or 'inspect the CTA layout'. Narrower than do: planner only targets endcard paths and knows the Luna.Unity.Playable.InstallFullGame() install action."""
        return await _run_kind(intent, "endcard", get_sampling, get_tool_registry, execute_batch_fn)
    maybe_expose(mcp, endcard, exposed)

    async def gameplay(intent: str) -> str:
        """Macro scoped to gameplay mechanics: Rigidbody, Collider, Animator, input simulation. Use for tasks like 'why isn't the character moving' or 'pause and inspect physics'. Planner will pause_game before inspection and can simulate_click for input."""
        return await _run_kind(intent, "gameplay", get_sampling, get_tool_registry, execute_batch_fn)
    maybe_expose(mcp, gameplay, exposed)

    async def monetization(intent: str) -> str:
        """Macro scoped to monetization: CTA buttons, Luna analytics events, MRAID SDK. Use for tasks like 'verify analytics fire on install click' or 'check MRAID is available'. Planner knows to check the console for analytics and eval typeof mraid."""
        return await _run_kind(intent, "monetization", get_sampling, get_tool_registry, execute_batch_fn)
    maybe_expose(mcp, monetization, exposed)

    return {
        "do":           (do,           None),
        "ask":          (ask,          None),
        "endcard":      (endcard,      None),
        "gameplay":     (gameplay,     None),
        "monetization": (monetization, None),
    }
