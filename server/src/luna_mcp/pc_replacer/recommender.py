"""Heuristic recommender: ranks unused modules by size."""
from __future__ import annotations

from .catalog import ModuleCatalog


class Recommender:
    def __init__(self, catalog: ModuleCatalog, sampling):
        self._catalog = catalog
        self._sampling = sampling  # reserved for future Haiku tier

    async def recommend(self, scan_result: dict, target_kb: int) -> str:
        """Returns text plan: ranked replacements to reach target savings."""
        candidates = []
        for module_id, info in scan_result.items():
            if info["usage"] != "unused":
                continue
            mod = self._catalog.get(module_id)
            evidence_count = info["evidence"].count("=defined") if info["evidence"] != "no probes" else 0
            confidence = 0.7 if evidence_count > 0 else 0.9
            candidates.append({
                "id": module_id,
                "save_kb": mod.size_kb if mod else info.get("size_kb", 0),
                "confidence": confidence,
                "reason": "unused (no instances)",
            })

        candidates.sort(key=lambda c: c["save_kb"], reverse=True)

        plan = []
        running = 0
        for c in candidates:
            plan.append(c)
            running += c["save_kb"]
            if running >= target_kb:
                break

        if not plan:
            return f"no safe replacements found (target {target_kb}kb, all modules in use)"

        lines = [f"target_save_kb={target_kb} achievable_kb={running}"]
        for c in plan:
            lines.append(
                f"  {c['id']} -> stub (save {c['save_kb']}kb, conf {c['confidence']:.2f}, {c['reason']})"
            )
        return "\n".join(lines)
