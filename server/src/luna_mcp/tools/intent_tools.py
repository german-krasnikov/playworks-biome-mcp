"""F13 Intent Router tools."""
from __future__ import annotations

from typing import Callable

from luna_mcp.intent_router.router import route

from . import maybe_expose


def register_intent_tools(
    mcp,
    exposed: set,
    sampling,
    tool_names: list,
    execute_fn: Callable,
) -> dict:
    async def route_intent(intent: str, path: str = "") -> str:
        """Dispatch a natural-language intent to the right tool. Tier 1: fast keyword match (no LLM cost). Tier 2: Haiku plan for complex intents. Prefer over do/ask for single-object tasks where you already know the path. Use do for multi-step discovery+mutation without a known path."""
        return await route(intent, path, sampling, tool_names, execute_fn)

    maybe_expose(mcp, route_intent, exposed)

    return {
        "route_intent": (route_intent, None),
    }
