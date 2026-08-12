"""Feature wiring called from server.py lifespan."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def wire_features(*, call_fn, sampling, ping_fn, lessons_store,
                  rec_data_dir, build_semantic, pc_validator, metrics,
                  all_tools: dict):
    """Wire feature-module singletons that depend on lifespan-created objects."""
    import luna_mcp.reflect.rules_modify as _reflect_modify
    import luna_mcp.reflect.rules_runtime as _reflect_runtime
    import luna_mcp.tools.flag_explorer_tools as _flag_mod
    import luna_mcp.tools.optimize_tools as _optimize_mod
    import luna_mcp.tools.physics_tools as _physics_mod
    import luna_mcp.tools.stats_tools as _stats_mod

    from .budget import visual_router as _visual_router_mod

    _stats_mod._metrics = metrics

    # Hidden Flags (F9)
    from .flag_explorer.catalog import FlagCatalog
    from .flag_explorer.recommender import FlagRecommender
    from .flag_explorer.seeds import seed_default as _seed_flags
    _flag_catalog = FlagCatalog(rec_data_dir / "flag_catalog.json")
    _seed_flags(_flag_catalog)
    _flag_mod._catalog = _flag_catalog
    _flag_mod._recommender = FlagRecommender(_flag_catalog)

    # F10 — wire F4/F5/F6
    from .optimize_macro.orchestrator import BuildOptimizer
    _optimize_mod._orchestrator = BuildOptimizer(
        jakefile_suggest_fn=all_tools.get("suggest_jakefile_patch", (None,))[0],
        pc_recommend_fn=all_tools.get("recommend_pc_replacements", (None,))[0],
        asset_recommend_fn=all_tools.get("recommend_asset_optimization", (None,))[0],
    )

    # Physics Detective
    from .lessons.luna_issue_seeds import seed_luna_issues
    from .physics_detective.diagnose_flow import PhysicsDiagnostic
    from .physics_detective.seeds import seed_physics_lessons
    if lessons_store is not None:
        try:
            seed_physics_lessons(lessons_store)
        except Exception:
            logger.debug("seed_physics_lessons failed", exc_info=True)
        try:
            seed_luna_issues(lessons_store)
        except Exception:
            logger.debug("seed_luna_issues failed", exc_info=True)
    _physics_mod._diagnostic = PhysicsDiagnostic(call_fn, sampling, lessons_store)
    _physics_mod._compare_states_fn = all_tools.get(
        "compare_animation_states", (None,))[0]
    _visual_router_mod._call_fn = call_fn
    _reflect_modify._call_fn = call_fn
    _reflect_runtime._ping_fn = ping_fn

    # Wire sampling into build diff
    build_semantic._sampling = sampling
    # Wire visual_baseline_check into PC validator
    _vbc_fn = all_tools.get("visual_baseline_check", (None,))[0]
    if _vbc_fn is not None:
        pc_validator._check = _vbc_fn
