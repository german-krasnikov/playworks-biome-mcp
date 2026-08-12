"""F18: Auto-Playtest Script Generator tools."""
from __future__ import annotations

from typing import Callable, Optional

from luna_mcp.playtest.generator import generate_playtest_script

from . import maybe_expose


def register_playtest_tools(
    mcp,
    get_sampling: Callable,
    get_tool_registry: Callable,
    exposed: set,
    execute_batch_fn: Optional[Callable] = None,
) -> dict:
    """Register generate_playtest (exposed) and run_generated_playtest (batch-only)."""
    if execute_batch_fn is None:
        from luna_mcp.tools.batch import execute_batch
        execute_batch_fn = execute_batch

    async def generate_playtest(intent: str) -> str:
        """Generate a batch DSL playtest script from a plain-English intent."""
        return await generate_playtest_script(
            intent,
            sampling=get_sampling(),
            tool_registry=get_tool_registry(),
            execute_batch_fn=execute_batch_fn,
        )
    maybe_expose(mcp, generate_playtest, exposed)

    async def run_generated_playtest(script: str) -> str:
        """Execute a previously generated playtest script."""
        return await execute_batch_fn(script)
    maybe_expose(mcp, run_generated_playtest, exposed, name="run_generated_playtest")

    return {
        "generate_playtest":     (generate_playtest,     None),
        "run_generated_playtest": (run_generated_playtest, None),
    }
