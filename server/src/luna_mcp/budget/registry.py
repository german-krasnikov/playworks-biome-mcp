"""Tool cost registry: token estimates + tier classification."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ToolCost:
    est_in: int
    est_out: int
    tier: str          # trivial|cheap|mid|expensive
    downgrade: str | None = None


TOOL_COSTS: dict[str, ToolCost] = {
    "ping":                  ToolCost(20,   10,    "trivial"),
    "get_connection_info":   ToolCost(50,   80,    "trivial"),
    "get_hierarchy":         ToolCost(100,  5000,  "mid",       None),
    "find_objects":          ToolCost(100,  400,   "cheap"),
    "get_component":         ToolCost(150,  600,   "cheap"),
    "get_object_detail":     ToolCost(150,  1500,  "mid",       "get_component"),
    "diagnose_object":       ToolCost(200,  2000,  "mid"),
    "get_performance_metrics": ToolCost(100, 400,  "cheap"),
    "diagnose_rendering":    ToolCost(150,  2000,  "mid",       "get_performance_metrics"),
    "diagnose_bottlenecks":  ToolCost(150,  1500,  "mid"),
    "get_render_stats":      ToolCost(100,  500,   "cheap"),
    "get_console":           ToolCost(100,  800,   "cheap"),
    "screenshot":            ToolCost(400,  12000, "expensive", "analyze_visual"),
    "screenshot_som":        ToolCost(400,  8000,  "expensive", "analyze_visual"),
    "eval_js":               ToolCost(200,  500,   "cheap"),
    "audit_textures":        ToolCost(100,  3000,  "mid"),
    "analyze_build":         ToolCost(100,  4000,  "mid",       "get_build_assets"),
    "set_property":          ToolCost(100,  200,   "cheap"),
    "set_transform":         ToolCost(100,  200,   "cheap"),
    "visual_summary":        ToolCost(100,  200,   "cheap"),
    "analyze_screenshot":    ToolCost(400,  300,   "mid"),
    "verify_visual_state":   ToolCost(400,  100,   "mid"),
    "describe_playable":     ToolCost(400,  200,   "mid"),
    "watch":                 ToolCost(150,  200,   "cheap"),
    "stream_until":          ToolCost(150,  100,   "cheap"),
    "get_events":            ToolCost(50,   800,   "cheap"),
    "set_event_filter":      ToolCost(50,   30,    "trivial"),
    "template":              ToolCost(50,   1500,  "mid"),
    "template_list":         ToolCost(30,   500,   "cheap"),
    "template_save":         ToolCost(50,   50,    "trivial"),
    "visual_baseline_save":        ToolCost(400, 200, "expensive", "visual_summary"),
    "visual_baseline_check":       ToolCost(400, 100, "mid"),
    "visual_baseline_list":        ToolCost(50,  200, "trivial"),
    "visual_baseline_invalidate":  ToolCost(50,  50,  "trivial"),
    # Timeline tools
    "motion_summary":           ToolCost(150, 100,  "cheap"),
    "capture_timeline":         ToolCost(400, 200,  "expensive", "motion_summary"),
    "analyze_animation":        ToolCost(800, 200,  "expensive", "motion_summary"),
    "compare_animation_states": ToolCost(800, 300,  "expensive", "motion_summary"),
    # Macro tools (Haiku planner + batch execution)
    "do":           ToolCost(800, 2000, "expensive"),
    "ask":          ToolCost(800, 1500, "mid"),
    "endcard":      ToolCost(800, 2500, "expensive"),
    "gameplay":     ToolCost(800, 2500, "expensive"),
    "monetization": ToolCost(800, 2500, "expensive"),
    # Record/replay tools
    "record_start": ToolCost(50,  50,   "trivial"),
    "record_stop":  ToolCost(50,  50,   "trivial"),
    "record_list":  ToolCost(50,  200,  "trivial"),
    "replay":       ToolCost(200, 1000, "mid"),
    "record_diff":  ToolCost(200, 1000, "mid"),
    # Physics Detective tools
    "detect_physics_backend": ToolCost(50,  200, "trivial"),
    "diagnose_physics":       ToolCost(150, 500, "cheap"),
    "physics_health_check":   ToolCost(50,  200, "cheap"),
    "compare_physics_states": ToolCost(800, 300, "expensive", "motion_summary"),
    # Build Diff Analyzer tools
    "index_build":   ToolCost(50,  200, "trivial"),
    "diff_builds":   ToolCost(200, 2000, "mid"),
    "list_builds":   ToolCost(50,  500, "trivial"),
    "bisect_change": ToolCost(150, 800, "mid"),
    # Jakefile Intelligence tools (F4)
    "analyze_jakefile":       ToolCost(50,  1000, "cheap"),
    "suggest_jakefile_patch": ToolCost(800, 1500, "expensive"),
    "apply_jakefile_patch":   ToolCost(100, 300,  "mid"),
    "revert_jakefile_patch":  ToolCost(50,  200,  "cheap"),
    # PC Module Replacer tools (F5)
    "audit_pc_modules":          ToolCost(50,  800, "cheap"),
    "recommend_pc_replacements": ToolCost(100, 500, "cheap"),
    "apply_pc_replacement":      ToolCost(100, 200, "cheap"),
    "validate_pc_replacement":   ToolCost(400, 200, "mid"),
    "revert_pc_replacement":     ToolCost(50,  100, "trivial"),
    # Asset Pipeline Co-pilot tools (F6)
    "audit_assets":                  ToolCost(50,  1500, "cheap"),
    "analyze_texture":               ToolCost(50,  300,  "cheap"),
    "recommend_asset_optimization":  ToolCost(100, 2000, "mid"),
    "apply_asset_optimization":      ToolCost(50,  200,  "trivial"),
    # Hidden Flags Explorer tools (F9)
    "discover_flags":    ToolCost(50, 800, "cheap"),
    "list_flag_catalog": ToolCost(50, 800, "cheap"),
    "lookup_flag":       ToolCost(50, 300, "trivial"),
    "recommend_flags":   ToolCost(50, 600, "trivial"),
    # Build Optimization Macro tools (F10)
    "optimize_build_size": ToolCost(800, 3000, "expensive"),
    "optimize_status":     ToolCost(50,  200,  "trivial"),
    # Luna Config tools (C4)
    "luna_config_get":  ToolCost(50,  800,  "cheap"),
    "luna_config_diff": ToolCost(80,  600,  "cheap"),
    "luna_config_set":  ToolCost(100, 200,  "cheap"),
    "jake_build":       ToolCost(100, 400,  "mid"),
}

DEFAULT = ToolCost(150, 800, "mid", None)

# Merge extended cost table (avoids 200-LOC limit on this file)
from .costs import EXTRA_TOOL_COSTS as _EXTRA  # noqa: E402

TOOL_COSTS.update(_EXTRA)


def cost_of(name: str, params: dict) -> ToolCost:
    base = TOOL_COSTS.get(name, DEFAULT)
    if name == "get_hierarchy":
        depth = int(params.get("depth", 1) or 1)
        if depth >= 4:
            return replace(base, est_out=5000)
        if depth <= 2:
            return replace(base, est_out=500, tier="cheap")
    if name == "eval_js":
        expr = params.get("expression", "")
        if "JSON.stringify" in expr or "dump" in expr.lower():
            return replace(base, est_out=8000, tier="expensive")
    return base
