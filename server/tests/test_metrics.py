"""Tests for MetricsRegistry and sinks."""
import json

from luna_mcp.budget.metrics import MetricsRegistry
from luna_mcp.budget.sinks import JsonlSink, NullSink

# --- MetricsRegistry ---

def test_record_call_updates_spent():
    m = MetricsRegistry(cap=1000)
    m.record_call("foo", 100, 10.0)
    assert m.spent == 100


def test_record_call_appends_latency():
    m = MetricsRegistry()
    m.record_call("foo", 10, 42.5)
    m.record_call("foo", 10, 55.0)
    assert len(m._latencies["foo"]) == 2
    assert 42.5 in m._latencies["foo"]


def test_record_call_appends_token_hist():
    m = MetricsRegistry()
    m.record_call("foo", 123, 1.0)
    assert 123 in m._tokens_hist["foo"]


def test_record_call_increments_error():
    m = MetricsRegistry()
    m.record_call("foo", 0, 1.0, error="TimeoutError")
    m.record_call("foo", 0, 1.0, error="TimeoutError")
    assert m._errors["foo"]["TimeoutError"] == 2


def test_record_call_no_error_by_default():
    m = MetricsRegistry()
    m.record_call("bar", 10, 5.0)
    assert "bar" not in m._errors


def test_p50_latency():
    m = MetricsRegistry()
    for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
        m.record_call("x", 0, v)
    p50 = m.p50_latency("x")
    assert p50 == 30.0


def test_p95_latency():
    m = MetricsRegistry()
    for v in range(1, 101):
        m.record_call("x", 0, float(v))
    p95 = m.p95_latency("x")
    assert p95 >= 95.0


def test_p50_returns_none_when_no_data():
    m = MetricsRegistry()
    assert m.p50_latency("missing") is None


def test_p95_returns_none_when_no_data():
    m = MetricsRegistry()
    assert m.p95_latency("missing") is None


def test_errors_for_empty():
    m = MetricsRegistry()
    assert m.errors_for("nonexistent") == {}


def test_errors_for_returns_copy():
    m = MetricsRegistry()
    m.record_call("t", 0, 1.0, error="E")
    d = m.errors_for("t")
    d["E"] = 999
    assert m._errors["t"]["E"] == 1  # original unchanged


def test_format_report_includes_budget():
    m = MetricsRegistry(cap=1000)
    m.record_call("slow", 200, 500.0)
    report = m.format_report()
    assert "200/1000" in report


def test_format_report_includes_top_slow():
    m = MetricsRegistry()
    for v in [100.0, 200.0, 300.0]:
        m.record_call(f"tool_{v}", 0, v)
    report = m.format_report()
    assert "Slowest p95" in report


def test_format_report_includes_top_errors():
    m = MetricsRegistry()
    for _ in range(3):
        m.record_call("bad", 0, 1.0, error="Err")
    report = m.format_report()
    assert "Top errors" in report


def test_null_sink_is_default():
    m = MetricsRegistry()
    assert isinstance(m._sink, NullSink)


def test_custom_sink_receives_events():
    received = []

    class CaptureSink:
        def emit(self, event):
            received.append(event)

    m = MetricsRegistry(sink=CaptureSink())
    m.record_call("foo", 50, 5.0)
    assert len(received) == 1
    assert received[0]["tool"] == "foo"
    assert received[0]["cost"] == 50


def test_jsonl_sink_writes(tmp_path):
    p = tmp_path / "metrics.jsonl"
    sink = JsonlSink(p, batch_size=1)
    sink.emit({"tool": "foo", "cost": 10})
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["tool"] == "foo"


def test_jsonl_sink_batches(tmp_path):
    p = tmp_path / "metrics.jsonl"
    sink = JsonlSink(p, batch_size=3)
    sink.emit({"n": 1})
    sink.emit({"n": 2})
    # not flushed yet
    assert not p.exists() or p.read_text() == ""
    sink.emit({"n": 3})  # triggers flush
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 3


def test_jsonl_sink_close_flushes(tmp_path):
    p = tmp_path / "m.jsonl"
    sink = JsonlSink(p, batch_size=10)
    sink.emit({"x": 1})
    sink.close()
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 1


def test_null_sink_emits_nothing():
    sink = NullSink()
    sink.emit({"tool": "x"})  # should not raise


def test_metrics_inherits_budget_tracker():
    from luna_mcp.budget.tracker import BudgetTracker
    m = MetricsRegistry(cap=500)
    assert isinstance(m, BudgetTracker)


def test_latency_deque_maxlen():
    m = MetricsRegistry()
    for i in range(300):
        m.record_call("t", 0, float(i))
    assert len(m._latencies["t"]) == 256


# ── M1: MetricsRegistry.close() flushes JsonlSink ────────────────────────────

def test_metrics_close_flushes_sink(tmp_path):
    """M1: close() must flush buffered events to file (batch_size=10, emit 3)."""
    p = tmp_path / "metrics.jsonl"
    sink = JsonlSink(p, batch_size=10)
    m = MetricsRegistry(cap=1000, sink=sink)
    for i in range(3):
        m.record_call(f"tool_{i}", 10, 5.0)
    # Not flushed yet (batch_size=10)
    assert not p.exists() or p.stat().st_size == 0
    m.close()
    lines = [l for l in p.read_text().strip().split("\n") if l]
    assert len(lines) == 3


# ── M3: _budget_tracker is same object as _metrics ───────────────────────────

def test_budget_tracker_is_metrics_registry():
    """M3: after module init, _budget_tracker must be the same object as _metrics."""
    import luna_mcp.server as srv
    assert srv._budget_tracker is srv._metrics


def test_router_decisions_use_same_spent_as_metrics():
    """M3: spending via record_call on _metrics is visible to router (same tracker)."""
    import luna_mcp.server as srv
    # router was created with _budget_tracker — check they share state
    before = srv._metrics.spent
    srv._metrics.record_call("ping", 50, 1.0)
    after = srv._metrics.spent
    assert after == before + 50
    # _budget_tracker.spent reflects same value
    assert srv._budget_tracker.spent == after
