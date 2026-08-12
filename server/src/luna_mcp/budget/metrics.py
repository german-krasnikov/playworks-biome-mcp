"""MetricsRegistry: BudgetTracker + per-tool latency/errors/token histograms."""
import time
from collections import deque
from typing import Optional

from .sinks import NullSink, Sink
from .tracker import BudgetTracker


class MetricsRegistry(BudgetTracker):
    """Extends BudgetTracker with per-tool latency, errors, token histograms."""

    def __init__(self, cap: int = 30_000, sink: Optional[Sink] = None):
        super().__init__(cap=cap)
        self._latencies: dict = {}
        self._errors: dict = {}
        self._tokens_hist: dict = {}
        self._counts: dict = {}  # per-tool invocation counters (C5b)
        self._sink: Sink = sink or NullSink()

    def record_call(self, name: str, cost: int, latency_ms: float, error: Optional[str] = None) -> None:
        super().record(name, cost)
        self._latencies.setdefault(name, deque(maxlen=256)).append(latency_ms)
        self._tokens_hist.setdefault(name, deque(maxlen=256)).append(cost)
        self._counts[name] = self._counts.get(name, 0) + 1
        if error:
            bucket = self._errors.setdefault(name, {})
            bucket[error] = bucket.get(error, 0) + 1
        self._sink.emit({"ts": time.time(), "tool": name, "cost": cost, "latency_ms": latency_ms, "error": error})

    def call_count(self, name: str) -> int:
        """Return invocation count for a tool (0 if never called)."""
        return self._counts.get(name, 0)

    def call_counts_all(self) -> dict:
        """Return copy of all per-tool invocation counts."""
        return dict(self._counts)

    def p50_latency(self, name: str) -> Optional[float]:
        lat = self._latencies.get(name)
        if not lat:
            return None
        s = sorted(lat)
        return s[len(s) // 2]

    def p95_latency(self, name: str) -> Optional[float]:
        lat = self._latencies.get(name)
        if not lat:
            return None
        s = sorted(lat)
        return s[min(len(s) - 1, int(len(s) * 0.95))]

    def errors_for(self, name: str) -> dict:
        return dict(self._errors.get(name, {}))

    def close(self) -> None:
        if hasattr(self._sink, "close"):
            self._sink.close()

    def format_report(self) -> str:
        lines = [f"Budget: {self.spent}/{self.cap} ({self.pct()*100:.0f}%) | {len(self._latencies)} tools tracked"]
        slowest = sorted(
            self._latencies.items(),
            key=lambda kv: self.p95_latency(kv[0]) or 0,
            reverse=True,
        )[:3]
        if slowest:
            lines.append("Slowest p95: " + ", ".join(f"{n}={self.p95_latency(n):.0f}ms" for n, _ in slowest))
        top_errors = sorted(
            ((n, sum(d.values())) for n, d in self._errors.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        if top_errors:
            lines.append("Top errors: " + ", ".join(f"{n}({c})" for n, c in top_errors))
        top_calls = sorted(self._counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        if top_calls:
            lines.append("Top calls: " + ", ".join(f"{n}={c}" for n, c in top_calls))
        return "\n".join(lines)
