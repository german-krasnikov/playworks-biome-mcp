"""CombinedPlan estimator — aggregates F4+F5+F6 savings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class OptimizationSource:
    name: str  # "jakefile" | "pc_modules" | "assets"
    estimated_save_kb: int
    actions_count: int
    summary: str  # short text describing strategy
    wire_size_kb: int | None = None   # brotli-compressed estimate (None = unknown)
    wire_label: str | None = None     # "brotli-compressed" | "uncompressed/heuristic" | None


@dataclass
class CombinedPlan:
    target_kb: int
    sources: List[OptimizationSource] = field(default_factory=list)

    def total_save_kb(self) -> int:
        return sum(s.estimated_save_kb for s in self.sources)

    def to_text(self) -> str:
        lines = [f"target_save_kb={self.target_kb} estimated_total={self.total_save_kb()}kb"]
        for s in self.sources:
            lines.append(f"\n[{s.name}] save~{s.estimated_save_kb}kb actions={s.actions_count}")
            lines.append(f"  {s.summary}")
            if s.wire_size_kb is not None and s.wire_label:
                lines.append(f"  wire~{s.wire_size_kb}kb ({s.wire_label})")
        if self.total_save_kb() < self.target_kb:
            lines.append(
                f"\nWARNING: estimated savings ({self.total_save_kb()}kb) < target ({self.target_kb}kb)"
            )
        return "\n".join(lines)
