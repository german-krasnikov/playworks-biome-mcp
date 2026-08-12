"""Tests for F12 Compliance Checker — RED phase."""
from __future__ import annotations

import pathlib

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_build(tmp_path: pathlib.Path, size_bytes: int, has_mraid: bool = True) -> pathlib.Path:
    """Create a minimal fake build directory."""
    index = tmp_path / "index.html"
    index.write_text("<html></html>")
    asset = tmp_path / "main.js"
    asset.write_bytes(b"x" * size_bytes)
    if has_mraid:
        (tmp_path / "mraid.js").write_text("// mraid")
    return tmp_path


# ---------------------------------------------------------------------------
# Tier 1: check_tier1
# ---------------------------------------------------------------------------

def test_size_fail_meta(tmp_path):
    build = _make_build(tmp_path, size_bytes=3 * 1024 * 1024)  # 3 MB > 2 MB limit
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "meta")
    size_check = next(r for r in results if r[0] == "size")
    assert size_check[1] is False


def test_size_pass_meta(tmp_path):
    build = _make_build(tmp_path, size_bytes=1 * 1024 * 1024)  # 1 MB < 2 MB limit
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "meta")
    size_check = next(r for r in results if r[0] == "size")
    assert size_check[1] is True


def test_mraid_fail_meta(tmp_path):
    build = _make_build(tmp_path, size_bytes=100 * 1024, has_mraid=False)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "meta")
    mraid_check = next(r for r in results if r[0] == "mraid")
    assert mraid_check[1] is False


def test_mraid_pass_meta(tmp_path):
    build = _make_build(tmp_path, size_bytes=100 * 1024, has_mraid=True)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "meta")
    mraid_check = next(r for r in results if r[0] == "mraid")
    assert mraid_check[1] is True


def test_mraid_not_checked_for_tiktok(tmp_path):
    """TikTok doesn't require mraid — should not appear in results."""
    build = _make_build(tmp_path, size_bytes=100 * 1024, has_mraid=False)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "tiktok")
    names = [r[0] for r in results]
    assert "mraid" not in names


def test_index_html_missing(tmp_path):
    # No index.html
    (tmp_path / "main.js").write_bytes(b"x" * 100)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(tmp_path), "meta")
    idx_check = next(r for r in results if r[0] == "index_html")
    assert idx_check[1] is False


def test_index_html_present(tmp_path):
    build = _make_build(tmp_path, size_bytes=100 * 1024)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "meta")
    idx_check = next(r for r in results if r[0] == "index_html")
    assert idx_check[1] is True


def test_asset_count_reported(tmp_path):
    build = _make_build(tmp_path, size_bytes=100 * 1024)
    from luna_mcp.compliance.checker import check_tier1
    results = check_tier1(str(build), "google")
    asset_check = next(r for r in results if r[0] == "assets")
    assert asset_check is not None
    assert isinstance(asset_check[2], str)


# ---------------------------------------------------------------------------
# format_results
# ---------------------------------------------------------------------------

def test_format_results_pass():
    from luna_mcp.compliance.checker import format_results
    checks = [("size", True, "1.0MB / 2MB"), ("mraid", True, "found")]
    out = format_results(checks)
    assert "[PASS] size" in out
    assert "[PASS] mraid" in out


def test_format_results_fail():
    from luna_mcp.compliance.checker import format_results
    checks = [("size", False, "3.0MB / 2MB")]
    out = format_results(checks)
    assert "[FAIL] size" in out


# ---------------------------------------------------------------------------
# check_compliance tool (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_compliance_all_pass(tmp_path):
    build = _make_build(tmp_path, size_bytes=500 * 1024)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "meta")
    assert "[PASS]" in result
    assert "[FAIL]" not in result


@pytest.mark.asyncio
async def test_check_compliance_size_fail(tmp_path):
    build = _make_build(tmp_path, size_bytes=3 * 1024 * 1024)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "meta")
    assert "[FAIL] size" in result


@pytest.mark.asyncio
async def test_check_compliance_mraid_fail(tmp_path):
    build = _make_build(tmp_path, size_bytes=500 * 1024, has_mraid=False)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "meta")
    assert "[FAIL] mraid" in result


@pytest.mark.asyncio
async def test_check_compliance_unknown_network(tmp_path):
    build = _make_build(tmp_path, size_bytes=100 * 1024)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "unknown_net")
    assert "error" in result.lower() or "unknown" in result.lower()


@pytest.mark.asyncio
async def test_check_compliance_no_screenshot(tmp_path):
    """Without screenshot_path, only Tier 1 runs — no LLM call."""
    build = _make_build(tmp_path, size_bytes=500 * 1024)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "google")
    assert result  # non-empty, no exception


@pytest.mark.asyncio
async def test_check_compliance_shows_network_name(tmp_path):
    build = _make_build(tmp_path, size_bytes=500 * 1024)
    from luna_mcp.tools.compliance_tools import check_compliance
    result = await check_compliance(str(build), "applovin")
    assert "applovin" in result.lower()


# ---------------------------------------------------------------------------
# NETWORK_RULES smoke test
# ---------------------------------------------------------------------------

def test_all_networks_defined():
    from luna_mcp.compliance.checker import NETWORK_RULES
    expected = {"meta", "google", "tiktok", "applovin", "unity_ads", "ironsource"}
    assert expected == set(NETWORK_RULES.keys())


def test_network_rules_schema():
    from luna_mcp.compliance.checker import NETWORK_RULES
    for name, rules in NETWORK_RULES.items():
        assert "max_size_mb" in rules, f"{name} missing max_size_mb"
        assert "require_mraid" in rules, f"{name} missing require_mraid"
        assert "format" in rules, f"{name} missing format"
