"""Tool wiring: imports, EXPOSED_TOOLS, and register_all_tools factory."""
from __future__ import annotations

import pathlib

from mcp.server.fastmcp import FastMCP

import luna_mcp.tools.distiller_tools as _distiller_mod

from .budget import BudgetTracker, ToolRouter
from .config import data_dir as _cfg_data_dir
from .regression.store import BaselineStore
from .regression.tools import register_regression_tools
from .sampling import SamplingService
from .tools.analysis_tools import register_analysis_tools
from .tools.asset_tools import register_asset_tools
from .tools.batch import execute_batch
from .tools.budget_tools import register_budget_tools
from .tools.build_diff_tools import register_build_diff_tools
from .tools.build_tools import register_build_tools
from .tools.compliance_tools import register_compliance_tools
from .tools.coverage_tools import register_coverage_tools
from .tools.cs_linter_tools import register_cs_linter_tools
from .tools.debug_native_tools import register_debug_native_tools
from .tools.debugger_tools import register_debugger_tools
from .tools.diagnostics_tools import register_diagnostics_tools
from .tools.distiller_tools import register_distiller_tools
from .tools.emulation_tools import register_emulation_tools
from .tools.events_tools import register_events_tools
from .tools.explainer_tools import register_explainer_tools
from .tools.flag_explorer_tools import register_flag_explorer_tools
from .tools.heap_tools import register_heap_tools
from .tools.input_tools import register_input_tools
from .tools.insights_tools import register_insights_tools
from .tools.intent_tools import register_intent_tools
from .tools.jake_tasks_tools import register_jake_tasks_tools
from .tools.jakefile_tools import register_jakefile_tools
from .tools.lifecycle_tools import register_lifecycle_tools
from .tools.llm_tools import register_llm_tools
from .tools.luna_config_tools import register_luna_config_tools
from .tools.macro_tools import register_macro_tools
from .tools.modify_tools import register_modify_tools
from .tools.netcond_tools import register_netcond_tools
from .tools.network_tools import register_network_tools
from .tools.optimize_tools import register_optimize_tools
from .tools.particle_tools import register_particle_tools
from .tools.pc_replacer_tools import register_pc_replacer_tools
from .tools.perf_tools import register_perf_tools
from .tools.physics_forensics_tools import register_physics_forensics_tools
from .tools.physics_tools import register_physics_tools
from .tools.playground_tools import register_playground_tools
from .tools.playtest_tools import register_playtest_tools
from .tools.playworks_tools import register_playworks_tools
from .tools.record_tools import register_record_tools
from .tools.reflection_tools import register_reflection_tools
from .tools.scene_tools import register_scene_tools
from .tools.som_tools import register_som_tools
from .tools.source_tools import register_source_tools
from .tools.state_tools import register_state_tools
from .tools.stats_tools import register_stats_tools
from .tools.tappable_tools import register_tappable_tools
from .tools.template_tools import register_template_tools
from .tools.text_tools import register_text_tools
from .tools.timeline_tools import register_timeline_tools
from .tools.trace_tools import register_trace_tools
from .tools.triage_tools import register_triage_tools
from .tools.tween_tools import register_tween_tools
from .tools.typemap_tools import register_typemap_tools
from .tools.visual_tools import register_visual_tools
from .tools.watchdog_tools import register_watchdog_tools


def merge_tool_groups(all_tools: dict, group: dict) -> dict:
    """Merge group into all_tools; raise ValueError on name collision."""
    dup = group.keys() & all_tools.keys()
    if dup:
        raise ValueError(f"Duplicate tool name(s): {sorted(dup)}")
    all_tools.update(group)
    return group


EXPOSED_TOOLS: set[str] = {
    "luna_config_get", "luna_config_diff",
    "get_hierarchy", "get_component", "get_object_detail", "find_objects",
    "find_objects_by_component",
    "set_property", "set_transform",
    "eval_js", "screenshot", "get_console",
    "diagnose_object", "pause_game", "resume_game",
    "get_performance_metrics", "diagnose_rendering",
    "analyze_build",
    "get_connection_info",
    "analyze_screenshot", "verify_visual_state", "describe_playable",
    "visual_summary",
    "motion_summary", "analyze_animation",
    "screenshot_som", "click_marker", "inspect_marker",
    "analyze_visual", "set_budget", "get_budget_status",
    "watch", "get_events",
    "template", "template_list", "template_save",
    "visual_baseline_save", "visual_baseline_check",
    "visual_baseline_list", "visual_baseline_invalidate",
    "mcp_stats",
    "do", "ask", "endcard", "gameplay", "monetization",
    "record_start", "record_stop", "record_list", "replay", "record_diff",
    "diagnose_physics", "physics_health_check",
    "index_build", "diff_builds", "list_builds",
    "audit_pc_modules", "recommend_pc_replacements",
    "audit_assets", "analyze_texture", "recommend_asset_optimization",
    "discover_flags", "list_flag_catalog", "recommend_flags",
    "optimize_build_size", "optimize_status",
    "cdp_perf_metrics",
    "audit_particles",
    "diagnose_text",
    "luna_debug_discover",
    "check_compliance",
    "distill_hierarchy",
    "explain_code", "explain_function",
    "generate_playtest", "run_generated_playtest",
    "watchdog_report",
    "triage_console",
    "route_intent",
    "insights_state", "insights_events",
    "why_not_tappable", "hit_test",
    "get_animator_graph", "get_luna_counters", "inspect_environment", "get_shader_variants",
    # S3.1 gestures
    "simulate_swipe",
    # S3.3 lifecycle
    "wait_for_lifecycle", "lifecycle_events",
    # S3.2 tween
    "tween_inventory", "tween_health",
    # S3.4 physics forensics
    "inspect_bodies", "physics_query",
    # S4.1 coverage
    "coverage_report",
    # S4.2 emulation
    "set_cpu_throttle", "set_device_metrics", "clear_emulation",
    # S4.3 tracing
    "trace_frames",
    # S4.4 heap
    "heap_sample",
    # S4.5 network conditions
    "set_network", "block_urls", "clear_network",
    # S5.2 C# linter
    "lint_csharp", "audit_required_apis",
    # S5.4 Jake tasks
    "discover_jake_tasks",
    # S6.1c GPU/startup probes
    "get_gpu_info", "get_vram_usage", "get_startup_timing",
    # S6.3 playground
    "get_playground_fields", "set_playground_field",
    # S6.6 step_frame
    "step_frame",
}


def register_all_tools(
    mcp: FastMCP,
    call_fn,
    send_fn,
    get_bridge,
    ensure_connected,
    require_debugger,
    require_source_mapper,
    get_typemap,
    budget_tracker: BudgetTracker,
    budget_router: ToolRouter,
    get_brain_scanner,
) -> tuple[dict, SamplingService]:
    """Register every tool group and return (_all_tools, sampling)."""
    all_tools: dict = {}

    merge_tool_groups(all_tools, register_scene_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_modify_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_diagnostics_tools(
        mcp, send_fn, call_fn, get_bridge, ensure_connected, exposed=EXPOSED_TOOLS
    ))
    merge_tool_groups(all_tools, register_perf_tools(mcp, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_emulation_tools(mcp, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_netcond_tools(mcp, get_bridge, ensure_connected, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_heap_tools(mcp, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_trace_tools(mcp, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_coverage_tools(mcp, get_bridge, require_source_mapper, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_debugger_tools(mcp, require_debugger, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_visual_tools(mcp, call_fn, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_reflection_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_input_tools(mcp, get_bridge, ensure_connected, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_network_tools(mcp, send_fn, get_bridge, ensure_connected, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_analysis_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_state_tools(mcp, call_fn, send_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_playworks_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_source_tools(mcp, require_source_mapper, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_build_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_typemap_tools(mcp, get_typemap, exposed=EXPOSED_TOOLS))

    sampling = SamplingService()
    merge_tool_groups(all_tools, register_llm_tools(mcp, sampling, get_bridge, exposed=EXPOSED_TOOLS))

    # SoM — after click/diagnose exist
    _click_fn = all_tools["simulate_click"][0]
    _diagnose_fn = all_tools["diagnose_object"][0]
    merge_tool_groups(all_tools, register_som_tools(mcp, call_fn, get_bridge, _click_fn, _diagnose_fn, exposed=EXPOSED_TOOLS))

    # Budget tools
    merge_tool_groups(all_tools, register_budget_tools(mcp, budget_tracker, budget_router, exposed=EXPOSED_TOOLS))

    merge_tool_groups(all_tools, register_events_tools(mcp, get_bridge, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_template_tools(mcp, exposed=EXPOSED_TOOLS))

    _baseline_store = BaselineStore()
    merge_tool_groups(all_tools, register_regression_tools(mcp, get_bridge, _baseline_store, sampling, exposed=EXPOSED_TOOLS))

    merge_tool_groups(all_tools, register_stats_tools(mcp, exposed=EXPOSED_TOOLS))

    from .timeline import _LabelCache as _TimelineLabelCache
    _timeline_cache = _TimelineLabelCache()
    merge_tool_groups(all_tools, register_timeline_tools(
        mcp,
        get_bridge=get_bridge,
        get_sampling=lambda: sampling,
        get_cache=lambda: _timeline_cache,
        exposed=EXPOSED_TOOLS,
    ))

    merge_tool_groups(all_tools, register_macro_tools(
        mcp,
        get_sampling=lambda: sampling,
        get_tool_registry=lambda: all_tools,
        exposed=EXPOSED_TOOLS,
    ))

    merge_tool_groups(all_tools, register_record_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_physics_tools(mcp, None, None, None, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_particle_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_text_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_debug_native_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))

    # Build Diff
    from .build_diff.router import TierRouter as _TierRouter
    from .build_diff.semantic_diff import SemanticDiff as _SemanticDiff
    from .build_diff.storage import BuildStore as _BuildStore
    from .build_diff.visual_diff import diff_pngs as _diff_pngs
    _build_store = _BuildStore(_cfg_data_dir() / "builds")
    build_semantic = _SemanticDiff(None)  # wired in lifespan
    _build_router = _TierRouter(build_semantic, _diff_pngs)
    merge_tool_groups(all_tools, register_build_diff_tools(mcp, _build_store, _build_router, exposed=EXPOSED_TOOLS))

    # Jakefile (F4)
    from .build_intel.planner import JakefilePlanner as _JakefilePlanner
    from .build_intel.store import PatchStore as _PatchStore
    _jake_shadow = _cfg_data_dir() / "jakefile_patches"
    _jake_store = _PatchStore(_cfg_data_dir() / "jakefile_patches.db")
    _jake_planner = _JakefilePlanner(sampling)
    merge_tool_groups(all_tools, register_jakefile_tools(
        mcp, planner=_jake_planner, shadow_base=_jake_shadow, store=_jake_store, exposed=EXPOSED_TOOLS
    ))

    # PC Module Replacer (F5)
    from .pc_replacer.applier import StubApplier as _StubApplier
    from .pc_replacer.catalog import ModuleCatalog as _ModuleCatalog
    from .pc_replacer.recommender import Recommender as _Recommender
    from .pc_replacer.scanner import UsageScanner as _UsageScanner
    from .pc_replacer.validator import Validator as _Validator
    _pc_catalog_path = pathlib.Path(__file__).parent / "pc_replacer" / "data" / "pc_modules.json"
    _pc_catalog = _ModuleCatalog(_pc_catalog_path)
    _pc_scanner = _UsageScanner(_pc_catalog, send_fn)
    _pc_recommender = _Recommender(_pc_catalog, sampling)
    _pc_applier = _StubApplier(send_fn)
    pc_validator = _Validator(None)  # wired in lifespan
    merge_tool_groups(all_tools, register_pc_replacer_tools(
        mcp, catalog=_pc_catalog, scanner=_pc_scanner,
        recommender=_pc_recommender, applier=_pc_applier,
        validator=pc_validator, exposed=EXPOSED_TOOLS,
    ))

    merge_tool_groups(all_tools, register_asset_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_flag_explorer_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_optimize_tools(mcp, exposed=EXPOSED_TOOLS))

    merge_tool_groups(all_tools, register_distiller_tools(mcp, exposed=EXPOSED_TOOLS))
    _distiller_mod._sampling = sampling

    merge_tool_groups(all_tools, register_compliance_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_explainer_tools(
        mcp, call_fn, typemap=None, sampling=sampling, exposed=EXPOSED_TOOLS
    ))

    merge_tool_groups(all_tools, register_playtest_tools(
        mcp,
        get_sampling=lambda: sampling,
        get_tool_registry=lambda: all_tools,
        exposed=EXPOSED_TOOLS,
        execute_batch_fn=execute_batch,
    ))

    merge_tool_groups(all_tools, register_watchdog_tools(mcp, get_brain_scanner=get_brain_scanner, exposed=EXPOSED_TOOLS))

    merge_tool_groups(all_tools, register_triage_tools(
        mcp,
        get_console_fn=lambda **kw: all_tools["get_console"][0](**kw),
        get_sampling=lambda: sampling,
        exposed=EXPOSED_TOOLS,
    ))

    # Luna config tools (C4)
    merge_tool_groups(all_tools, register_luna_config_tools(mcp, exposed=EXPOSED_TOOLS))

    # Sprint 2 additions
    merge_tool_groups(all_tools, register_insights_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_tappable_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))

    # Sprint 3 additions
    merge_tool_groups(all_tools, register_lifecycle_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_tween_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_physics_forensics_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))

    # Sprint 5 additions
    merge_tool_groups(all_tools, register_cs_linter_tools(mcp, exposed=EXPOSED_TOOLS))
    merge_tool_groups(all_tools, register_jake_tasks_tools(mcp, exposed=EXPOSED_TOOLS))

    # Sprint 6 additions
    merge_tool_groups(all_tools, register_playground_tools(mcp, call_fn, exposed=EXPOSED_TOOLS))

    # Intent Router last — so tool_names covers all registered tools
    merge_tool_groups(all_tools, register_intent_tools(
        mcp,
        exposed=EXPOSED_TOOLS,
        sampling=sampling,
        tool_names=list(all_tools.keys()),
        execute_fn=execute_batch,
    ))

    orphans = EXPOSED_TOOLS - set(all_tools.keys())
    if orphans:
        raise ValueError(f"EXPOSED_TOOLS references unknown tools: {orphans}")

    return all_tools, sampling, build_semantic, pc_validator
