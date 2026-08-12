"""4 MCP tools for Asset Pipeline Co-pilot (F6)."""
from __future__ import annotations

import pathlib

from ..asset_optimizer.catalog import AssetCatalog
from ..asset_optimizer.plan import OptimizationPlan, make_plan
from ..asset_optimizer.recommender import Recommender
from ..asset_optimizer.texture_analyzer import TextureAnalyzer
from ..tools import maybe_expose

# Module-level singletons (wired by server.py or created lazily here)
_texture_analyzer: TextureAnalyzer = TextureAnalyzer()
_recommender: Recommender = Recommender(_texture_analyzer)
_plan_store: dict[str, OptimizationPlan] = {}
_PLAN_STORE_MAX = 100


def _store_plan(plan: OptimizationPlan) -> None:
    if len(_plan_store) >= _PLAN_STORE_MAX:
        _plan_store.pop(next(iter(_plan_store)))  # FIFO eviction
    _plan_store[plan.plan_id] = plan


async def audit_assets(path: str) -> str:
    """Walk asset dir, return kind summary and top-10 by size."""
    p = pathlib.Path(path).expanduser().resolve()
    try:
        catalog = AssetCatalog(p)
    except ValueError as e:
        return f"[INVALID: {e}]"
    assets = catalog.scan()
    total = catalog.total_size(assets)
    by_kind = catalog.by_kind(assets)
    lines = [f"root={p}", f"total: {len(assets)} files, {total // 1024}kb"]
    for kind in ("texture", "audio", "font", "mesh", "other"):
        items = by_kind.get(kind, [])
        if items:
            kb = sum(a.size for a in items) // 1024
            lines.append(f"  {kind}: {len(items)} files, {kb}kb")
    lines.append("\ntop 10 by size:")
    for a in assets[:10]:
        lines.append(f"  {a.kind:7} {a.size // 1024:5}kb {a.path}")
    return "\n".join(lines)


async def analyze_texture(abs_path: str) -> str:
    """Single-texture deep analysis: dimensions, entropy, classification."""
    p = pathlib.Path(abs_path).expanduser().resolve()
    if not p.exists():
        return f"[INVALID: file not found: {p}]"
    info = _texture_analyzer.analyze(str(p))
    return (
        f"path={info.path}\n"
        f"size={info.width}x{info.height} pixels={info.pixels}\n"
        f"alpha={info.has_alpha} entropy={info.entropy:.2f}\n"
        f"classification={info.classification}"
    )


async def recommend_asset_optimization(path: str, target_size_kb: int = 100) -> str:
    """Generate asset optimization plan targeting target_size_kb savings."""
    p = pathlib.Path(path).expanduser().resolve()
    try:
        catalog = AssetCatalog(p)
    except ValueError as e:
        return f"[INVALID: {e}]"
    assets = catalog.scan()
    actions = _recommender.recommend_textures(assets, target_size_kb)
    plan = make_plan(target_size_kb, actions)
    _store_plan(plan)
    return plan.to_text()


async def apply_asset_optimization(plan_id: str, dry_run: bool = True) -> str:
    """MVP — dry_run report only. Real apply requires jakefile patches (F4)."""
    plan = _plan_store.get(plan_id)
    if plan is None:
        return f"[INVALID: plan '{plan_id}' not found. Run recommend_asset_optimization first.]"
    if dry_run:
        total = sum(a.est_save_kb for a in plan.actions)
        return (
            f"DRY_RUN plan {plan_id}: {len(plan.actions)} actions, "
            f"total save ~{total}kb. Real apply requires jakefile patching (use F4 jakefile_tools)."
        )
    return "[DEGRADED:asset_optimizer:real apply not implemented in MVP — use F4 jakefile_tools to apply asset rules]"


def register_asset_tools(mcp, exposed: set[str]) -> dict:
    fns = [
        ("audit_assets",                 audit_assets,                 True),
        ("analyze_texture",              analyze_texture,              True),
        ("recommend_asset_optimization", recommend_asset_optimization, True),
        ("apply_asset_optimization",     apply_asset_optimization,     False),
    ]
    out = {}
    for name, fn, read_only in fns:
        maybe_expose(mcp, fn, exposed, name=name, read_only=read_only)
        out[name] = (fn, None)
    return out
