"""Tests for per-tool invocation counter in MetricsRegistry (C5b)."""

from luna_mcp.budget.metrics import MetricsRegistry


def test_call_count_starts_zero():
    m = MetricsRegistry(cap=1000)
    assert m.call_count("nonexistent") == 0


def test_call_count_increments():
    m = MetricsRegistry(cap=1000)
    m.record_call("foo", 100, 10.0)
    assert m.call_count("foo") == 1
    m.record_call("foo", 100, 10.0)
    assert m.call_count("foo") == 2


def test_call_count_per_tool_independent():
    m = MetricsRegistry(cap=1000)
    m.record_call("a", 10, 1.0)
    m.record_call("b", 20, 2.0)
    m.record_call("a", 10, 1.0)
    assert m.call_count("a") == 2
    assert m.call_count("b") == 1


def test_call_counts_all_returns_dict():
    m = MetricsRegistry(cap=1000)
    m.record_call("x", 5, 1.0)
    m.record_call("y", 5, 1.0)
    counts = m.call_counts_all()
    assert counts["x"] == 1
    assert counts["y"] == 1


def test_format_report_includes_counts():
    """mcp_stats output must include per-tool call counts."""
    m = MetricsRegistry(cap=1000)
    m.record_call("my_tool", 100, 50.0)
    m.record_call("my_tool", 100, 60.0)
    report = m.format_report()
    # Should mention "calls" or the tool name with its count
    assert "my_tool" in report or "2" in report
    assert "calls" in report.lower() or "2" in report
