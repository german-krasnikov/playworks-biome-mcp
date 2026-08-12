"""OptimizationPlan dataclass + serializer."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from .recommender import AssetAction


@dataclass
class OptimizationPlan:
    plan_id: str
    created_at: float
    target_size_kb: int
    actions: list[AssetAction] = field(default_factory=list)

    def to_text(self) -> str:
        if not self.actions:
            return f"no actions for target {self.target_size_kb}kb"
        total = sum(a.est_save_kb for a in self.actions)
        lines = [
            f"plan_id={self.plan_id} target={self.target_size_kb}kb actions={len(self.actions)}",
            f"total_save={total}kb",
        ]
        for a in self.actions[:20]:
            lines.append(f"  {a.action:15} {a.asset_path:40} -{a.est_save_kb:4}kb {a.risk:4} ({a.reason})")
        if len(self.actions) > 20:
            lines.append(f"  ... {len(self.actions) - 20} more")
        return "\n".join(lines)


def make_plan(target_size_kb: int, actions: list[AssetAction]) -> OptimizationPlan:
    plan_id = uuid.uuid4().hex[:12]
    return OptimizationPlan(
        plan_id=plan_id,
        created_at=time.time(),
        target_size_kb=target_size_kb,
        actions=actions,
    )
