"""F18: Auto-Playtest Script Generator.

Tier 1: keyword → pre-built template (no LLM).
Tier 2: Haiku plan() + dry_run validation.
"""
from __future__ import annotations

from typing import Callable, Optional

from luna_mcp.macro.planner import clean_dsl

TEMPLATES: dict[str, str] = {
    "load": "get_performance_metrics\nscreenshot\nget_console level=E count=10",
    "cta": "find_objects query=CTA\nfind_objects query=Install\nscreenshot\nget_console level=E count=5",
    "orientation": "screenshot\nget_console level=E count=5",
    "performance": "get_performance_metrics\nget_render_stats\naudit_textures\nget_vram_usage",
    "endcard": "find_objects query=EndCard\nfind_objects query=Packshot\nscreenshot",
}

_TOOL_LIST = (
    "get_hierarchy get_performance_metrics screenshot get_console "
    "find_objects find_objects_by_component get_component get_object_detail "
    "set_property set_transform diagnose_object diagnose_rendering "
    "audit_assets analyze_texture audit_pc_modules"
)

_SYSTEM_PROMPT = (
    "Generate a batch DSL playtest script. "
    "Use ONLY real tool names from this list: {tool_list}. "
    "One command per line, key=value args. No prose, no markdown."
)


def match_template(intent: str) -> Optional[str]:
    lower = intent.lower()
    for key, script in TEMPLATES.items():
        if key in lower:
            return script
    return None


async def generate_playtest_script(
    intent: str,
    sampling=None,
    tool_registry: Optional[dict] = None,
    execute_batch_fn: Optional[Callable] = None,
) -> str:
    """Generate a batch DSL playtest script for the given intent.

    Returns Tier 1 template if keyword matches, otherwise Haiku plan (Tier 2),
    or error string if neither is available.
    """
    # Tier 1: keyword match
    script = match_template(intent)
    if script:
        return script

    # Tier 2: Haiku
    if sampling is None or not sampling.enabled:
        return f"[NO_TEMPLATE] Cannot generate script for: {intent}"

    tool_list = " ".join(tool_registry.keys()) if tool_registry else _TOOL_LIST
    system = _SYSTEM_PROMPT.format(tool_list=tool_list)
    raw = await sampling.plan(intent, system)
    if not raw:
        return f"[NO_TEMPLATE] Cannot generate script for: {intent}"

    dsl = clean_dsl(raw)
    if not dsl:
        return f"[NO_TEMPLATE] Cannot generate script for: {intent}"

    # Validate via dry_run
    if execute_batch_fn:
        dry = await execute_batch_fn(dsl, dry_run=True)
        if "[BATCH ABORTED" in dry or "[INVALID:" in dry:
            return f"[NO_TEMPLATE] Cannot generate script for: {intent}"

    return dsl
