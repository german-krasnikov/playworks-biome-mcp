"""Adaptive tool router: run / downgrade / skip based on budget state."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .registry import ToolCost, cost_of
from .tracker import BudgetTracker


@dataclass
class Decision:
    action: str        # "run" | "downgrade" | "skip"
    target: str | None = None
    hint: str = ""


class ToolRouter:
    def __init__(self, tracker: BudgetTracker, sigmoid_p_success: Optional[float] = None,
                 calibrator=None):
        self.t = tracker
        self._p_success = sigmoid_p_success  # None = hard threshold mode
        self._calibrator = calibrator  # CostCalibrator | None

    def _calibrated_est_out(self, name: str, base_cost: ToolCost) -> int:
        """Return EMA-blended est_out if calibrator has ≥5 samples, else raw."""
        if self._calibrator is None:
            return base_cost.est_out
        return self._calibrator.calibrated_cost(name, base_cost.est_out)

    def _decide_sigmoid(self, name: str, params: dict, cost: ToolCost) -> Decision:
        from .autotune import allow_prob
        pct = self.t.pct()
        prob = allow_prob(pct, self._p_success or 0.85)
        thresholds = {"trivial": 0.05, "cheap": 0.2, "mid": 0.5, "expensive": 0.8}
        if prob < thresholds.get(cost.tier, 0.5):
            if cost.downgrade:
                self.t.record_downgrade(name)
                return Decision("downgrade", cost.downgrade, f"sigmoid prob={prob:.2f}")
            self.t.record_skip(name)
            return Decision("skip", hint=f"sigmoid prob={prob:.2f}")
        return Decision("run")

    def decide(self, name: str, params: dict) -> Decision:
        if os.environ.get("LUNA_BUDGET_DISABLED") == "1":
            return Decision("run")

        c = cost_of(name, params)

        if self._p_success is not None:
            return self._decide_sigmoid(name, params, c)

        est_out = self._calibrated_est_out(name, c)
        proj = c.est_in + est_out
        rem = self.t.remaining()
        pct = self.t.pct()

        # Hard stop: projected cost exceeds remaining for expensive tools
        if proj > rem and c.tier == "expensive":
            if c.downgrade:
                self.t.record_downgrade(name)
                return Decision("downgrade", c.downgrade,
                                f"budget {rem}t < {proj}t — using {c.downgrade}")
            self.t.record_skip(name)
            return Decision("skip", None, f"budget exhausted: {rem}t left")

        # 95%+: only trivial/cheap allowed
        if pct >= 0.95 and c.tier in ("mid", "expensive"):
            if c.downgrade:
                self.t.record_downgrade(name)
                return Decision("downgrade", c.downgrade, "budget 95%")
            self.t.record_skip(name)
            return Decision("skip", None, "budget 95% — only trivial allowed")

        # 80%+: kill expensive without downgrade
        if pct >= 0.80 and c.tier == "expensive" and not c.downgrade:
            self.t.record_skip(name)
            return Decision("skip", None, "budget 80% — expensive blocked")

        # 50%+: hint on expensive
        if pct >= 0.50 and c.tier == "expensive":
            alt = c.downgrade or "cheaper alt"
            return Decision("run", None,
                            f"hint: at {pct*100:.0f}% — consider {alt}")

        return Decision("run", None, "")
