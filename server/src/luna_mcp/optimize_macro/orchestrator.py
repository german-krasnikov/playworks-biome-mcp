"""BuildOptimizer — orchestrates F4+F5+F6 for unified build size optimization."""
from __future__ import annotations

import re
from typing import Callable, Optional

from .estimator import CombinedPlan, OptimizationSource

# TODO: allow env override LUNA_OPTIMIZE_SPLIT (e.g. "30,35,35")
DEFAULT_SPLIT = {"jakefile": 0.30, "pc_modules": 0.35, "assets": 0.35}


class BuildOptimizer:
    def __init__(
        self,
        jakefile_suggest_fn: Optional[Callable] = None,
        pc_recommend_fn: Optional[Callable] = None,
        asset_recommend_fn: Optional[Callable] = None,
    ):
        self._jakefile = jakefile_suggest_fn
        self._pc = pc_recommend_fn
        self._asset_recommend = asset_recommend_fn

    @property
    def has_jakefile(self) -> bool: return self._jakefile is not None
    @property
    def has_pc(self) -> bool: return self._pc is not None
    @property
    def has_assets(self) -> bool: return self._asset_recommend is not None

    async def optimize(
        self, target_kb: int, asset_path: str = "", split: Optional[dict] = None
    ) -> CombinedPlan:
        split = split or DEFAULT_SPLIT
        plan = CombinedPlan(target_kb=target_kb)

        jf_target = int(target_kb * split.get("jakefile", 0.30))
        plan.sources.append(await self._call_jakefile(jf_target))

        pc_target = int(target_kb * split.get("pc_modules", 0.35))
        plan.sources.append(await self._call_pc(pc_target))

        asset_target = int(target_kb * split.get("assets", 0.35))
        plan.sources.append(await self._call_asset(asset_target, asset_path))

        return plan

    async def _call_jakefile(self, target_kb: int) -> OptimizationSource:
        if self._jakefile is None:
            return OptimizationSource("jakefile", 0, 0, "[unavailable: no jakefile_tools]")
        try:
            intent = f"reduce JS bundle size by ~{target_kb}kb (compress, strip unused, lower JPEG quality)"
            text = await self._jakefile(intent)
            return self._parse_jakefile_response(text, target_kb)
        except Exception as e:
            return OptimizationSource("jakefile", 0, 0, f"[error: {str(e)[:100]}]")

    def _parse_jakefile_response(self, text: str, target_kb: int) -> OptimizationSource:
        # Heuristic estimate: ~target_kb/3 per detected patch. Note: regex matches both
        # PATCH keyword and [opN] bracket lines, so n_patches may double-count for
        # multi-op plans. Capped at target_kb. Estimate is intentionally rough.
        n_patches = len(re.findall(r"\bPATCH\b|^\s*\[\w+\]", text, re.MULTILINE))
        est = min(target_kb, max(0, n_patches * target_kb // 3)) if n_patches else 0
        first_line = text.split("\n")[0][:80] if text else "[empty]"
        return OptimizationSource("jakefile", est, n_patches, first_line)

    async def _call_pc(self, target_kb: int) -> OptimizationSource:
        if self._pc is None:
            return OptimizationSource("pc_modules", 0, 0, "[unavailable: no pc_replacer_tools]")
        try:
            text = await self._pc(target_kb)
            return self._parse_pc_response(text, target_kb)
        except Exception as e:
            return OptimizationSource("pc_modules", 0, 0, f"[error: {str(e)[:100]}]")

    def _parse_pc_response(self, text: str, target_kb: int) -> OptimizationSource:
        matches = re.findall(r"\(save (\d+)kb", text)
        total = sum(int(m) for m in matches)
        first_line = text.split("\n")[0][:80] if text else "[empty]"
        return OptimizationSource("pc_modules", total, len(matches), first_line)

    async def _call_asset(self, target_kb: int, path: str) -> OptimizationSource:
        if self._asset_recommend is None or not path:
            return OptimizationSource("assets", 0, 0, "[unavailable: no asset_path]")
        try:
            text = await self._asset_recommend(path, target_kb)
            return self._parse_asset_response(text, target_kb)
        except Exception as e:
            return OptimizationSource("assets", 0, 0, f"[error: {str(e)[:100]}]")

    def _parse_asset_response(self, text: str, target_kb: int) -> OptimizationSource:
        m = re.search(r"total_save=(\d+)kb", text)
        save = int(m.group(1)) if m else 0
        m2 = re.search(r"actions=(\d+)", text)
        n = int(m2.group(1)) if m2 else 0
        first_line = text.split("\n")[0][:80] if text else "[empty]"
        return OptimizationSource("assets", save, n, first_line)
