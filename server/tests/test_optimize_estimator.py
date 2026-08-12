"""Tests for CombinedPlan estimator (F10)."""
from luna_mcp.optimize_macro.estimator import CombinedPlan, OptimizationSource


def test_source_fields():
    s = OptimizationSource("jakefile", 100, 3, "compress JPEG")
    assert s.name == "jakefile"
    assert s.estimated_save_kb == 100
    assert s.actions_count == 3
    assert s.summary == "compress JPEG"


def test_combined_plan_total_save_sums_sources():
    plan = CombinedPlan(target_kb=500)
    plan.sources.append(OptimizationSource("jakefile", 100, 2, "a"))
    plan.sources.append(OptimizationSource("pc_modules", 150, 3, "b"))
    plan.sources.append(OptimizationSource("assets", 80, 1, "c"))
    assert plan.total_save_kb() == 330


def test_combined_plan_total_save_empty():
    plan = CombinedPlan(target_kb=200)
    assert plan.total_save_kb() == 0


def test_to_text_header_line():
    plan = CombinedPlan(target_kb=300)
    plan.sources.append(OptimizationSource("jakefile", 50, 1, "ok"))
    text = plan.to_text()
    assert "target_save_kb=300" in text
    assert "estimated_total=50kb" in text


def test_to_text_format_per_source():
    plan = CombinedPlan(target_kb=300)
    plan.sources.append(OptimizationSource("jakefile", 50, 2, "strip unused"))
    text = plan.to_text()
    assert "[jakefile]" in text
    assert "save~50kb" in text
    assert "actions=2" in text
    assert "strip unused" in text


def test_to_text_includes_warning_when_under_target():
    plan = CombinedPlan(target_kb=500)
    plan.sources.append(OptimizationSource("jakefile", 50, 1, "x"))
    text = plan.to_text()
    assert "WARNING" in text
    assert "50kb" in text
    assert "500kb" in text


def test_to_text_no_warning_when_at_or_above_target():
    plan = CombinedPlan(target_kb=100)
    plan.sources.append(OptimizationSource("jakefile", 150, 1, "x"))
    text = plan.to_text()
    assert "WARNING" not in text


def test_to_text_multiple_sources():
    plan = CombinedPlan(target_kb=200)
    plan.sources.append(OptimizationSource("jakefile", 50, 1, "a"))
    plan.sources.append(OptimizationSource("pc_modules", 80, 2, "b"))
    text = plan.to_text()
    assert "[jakefile]" in text
    assert "[pc_modules]" in text


def test_to_text_exact_target_no_warning():
    plan = CombinedPlan(target_kb=100)
    plan.sources.append(OptimizationSource("assets", 100, 1, "ok"))
    assert "WARNING" not in plan.to_text()
