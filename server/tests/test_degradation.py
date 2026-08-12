"""Tests for GracefulDegradation middleware."""
from unittest.mock import MagicMock

from luna_mcp.degradation import GracefulDegradation


def make_degrad(connected=True, typemap_loaded=True, skipped_count=0):
    bridge = MagicMock()
    bridge.connected = connected

    metrics = MagicMock()
    metrics.skipped = {"get_type_info": skipped_count}

    typemap = MagicMock()
    typemap.is_loaded = MagicMock(return_value=typemap_loaded)

    return GracefulDegradation(
        bridge_getter=lambda: bridge,
        metrics=metrics,
        typemap_resolver_getter=lambda: typemap,
    )


def test_l1_chrome_down_blocks_non_offline_tools():
    d = make_degrad(connected=False)
    result = d.check("get_hierarchy", {})
    assert result is not None
    assert "DEGRADED:chrome" in result
    assert "9222" in result


def test_l1_chrome_down_allows_analyze_build():
    d = make_degrad(connected=False)
    assert d.check("analyze_build", {}) is None


def test_l1_chrome_down_allows_ping():
    d = make_degrad(connected=False)
    assert d.check("ping", {}) is None


def test_l1_chrome_down_allows_get_connection_info():
    d = make_degrad(connected=False)
    assert d.check("get_connection_info", {}) is None


def test_l1_chrome_down_allows_template_list():
    d = make_degrad(connected=False)
    assert d.check("template_list", {}) is None


def test_l3_typemap_missing_after_2_skips_blocks_set_property():
    d = make_degrad(typemap_loaded=False, skipped_count=2)
    result = d.check("set_property", {})
    assert result is not None
    assert "DEGRADED:typemap" in result
    assert "LUNA_PLUGIN_PATH" in result


def test_l3_typemap_loaded_no_degrade():
    d = make_degrad(typemap_loaded=True, skipped_count=2)
    assert d.check("set_property", {}) is None


def test_l3_typemap_missing_skip_less_than_2_no_degrade():
    d = make_degrad(typemap_loaded=False, skipped_count=1)
    assert d.check("set_property", {}) is None


def test_l3_typemap_affects_get_class_api():
    d = make_degrad(typemap_loaded=False, skipped_count=2)
    result = d.check("get_class_api", {})
    assert result is not None
    assert "DEGRADED:typemap" in result


def test_no_degrade_when_all_healthy():
    d = make_degrad(connected=True, typemap_loaded=True, skipped_count=0)
    assert d.check("set_property", {}) is None
    assert d.check("get_hierarchy", {}) is None
    assert d.check("eval_js", {}) is None


def test_offline_safe_set_includes_template_list():
    d = make_degrad()
    safe = d._offline_safe()
    assert "template_list" in safe
    assert "template_save" in safe
    assert "analyze_build" in safe
    assert "ping" in safe


def test_bridge_none_blocks_non_offline_tools():
    d = GracefulDegradation(
        bridge_getter=lambda: None,
        metrics=None,
        typemap_resolver_getter=lambda: None,
    )
    result = d.check("get_hierarchy", {})
    assert result is not None
    assert "DEGRADED:chrome" in result
