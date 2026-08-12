"""F13 Intent Router — smart dispatcher: keyword Tier 1 + Haiku Tier 2."""
from __future__ import annotations

from typing import Callable, Optional

KEYWORD_ROUTES: dict[tuple, str] = {
    ("recompile", "rebuild", "jake", "task", "build script"): "discover_jake_tasks path={path}",
    ("fall", "collide", "physics", "rigidbody", "gravity"): "diagnose_physics symptom={intent}",
    ("slow", "lag", "fps", "performance", "frame"):         "get_performance_metrics\ndiagnose_rendering",
    ("error", "crash", "exception", "null"):                "get_console level=E count=30",
    ("visible", "see", "invisible", "hidden", "render"):    "diagnose_object path={path}",
    ("texture", "material", "shader", "pink", "black"):     "audit_materials\nget_shader_report",
    ("click", "tap", "button", "touch", "input"):           "get_canvas_info path={path}\nget_layers",
    ("animation", "animator", "state", "transition"):       "get_animator_state path={path}",
    ("memory", "heap", "leak", "vram"):                     "get_memory_info\nget_vram_usage\naudit_textures",
    ("size", "build", "asset", "compress"):                 "analyze_build path={path}",
    ("sound", "audio", "music", "mute"):                    "get_audio_sources",
}

_SYS_PROMPT = (
    "You are a batch DSL planner for a Luna/Unity debugger. "
    "Given user intent, output 1-5 tool calls as batch DSL lines (tool_name key=value). "
    "Available tools: {tools}. "
    "No prose, no markdown fences, only DSL lines."
)


def route_tier1(intent: str, path: str = "") -> Optional[str]:
    lower = intent.lower()
    for keywords, template in KEYWORD_ROUTES.items():
        if any(k in lower for k in keywords):
            return template.replace("{intent}", intent).replace("{path}", path)
    return None


async def route(
    intent: str,
    path: str,
    sampling,
    tool_names: list,
    execute_fn: Callable,
) -> str:
    if not intent or not intent.strip():
        return f"[NO_ROUTE] Could not determine tools for: {intent!r}"

    plan: Optional[str] = None

    if sampling and getattr(sampling, "enabled", False):
        sys_prompt = _SYS_PROMPT.format(tools=", ".join(tool_names))
        plan = await sampling.plan(intent, sys_prompt)
        if plan:
            dry = await execute_fn(plan, dry_run=True)
            if "[BATCH ABORTED" in dry or "[INVALID:" in dry:
                plan = None  # fall back to Tier 1

    if not plan:
        plan = route_tier1(intent, path)

    if not plan:
        return f"[NO_ROUTE] Could not determine tools for: {intent}"

    return await execute_fn(plan)
