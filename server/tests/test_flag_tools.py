"""RED: FlagExplorer MCP tools."""
import asyncio

import pytest

import luna_mcp.tools.flag_explorer_tools as ft


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Wire up fresh catalog + recommender for each test."""
    from luna_mcp.flag_explorer.catalog import FlagCatalog
    from luna_mcp.flag_explorer.recommender import FlagRecommender
    from luna_mcp.flag_explorer.seeds import seed_default
    catalog = FlagCatalog(tmp_path / "flags.json")
    seed_default(catalog)
    ft._catalog = catalog
    ft._recommender = FlagRecommender(catalog)
    yield
    ft._catalog = None
    ft._recommender = None


SAMPLE_JAKEFILE = """
var minify = luna.json["disableMinify"];
var solver = getOption("useUnstableSolver");
var compress = config["compressTexturesWebP"];
"""


@pytest.fixture
def jakefile(tmp_path):
    p = tmp_path / "Jakefile.js"
    p.write_text(SAMPLE_JAKEFILE)
    return p


# --- discover_flags ---

def test_discover_flags_valid_path(jakefile):
    result = run(ft.discover_flags(str(jakefile)))
    assert "discovered" in result
    assert "disableMinify" in result


def test_discover_flags_missing_path():
    result = run(ft.discover_flags("/nonexistent/Jakefile.js"))
    assert "[INVALID" in result


def test_discover_flags_empty_path_no_jakefile(monkeypatch):
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", "/nonexistent/Jakefile.js")
    result = run(ft.discover_flags(""))
    assert "[INVALID" in result


def test_discover_flags_shows_multiple_flags(jakefile):
    result = run(ft.discover_flags(str(jakefile)))
    assert "useUnstableSolver" in result
    assert "compressTexturesWebP" in result


def test_discover_flags_shows_location_counts(jakefile):
    result = run(ft.discover_flags(str(jakefile)))
    # should show something like "(1 locations: ...)"
    assert "location" in result


# --- list_flag_catalog ---

def test_list_catalog_returns_entries():
    result = run(ft.list_flag_catalog())
    assert "catalog:" in result
    assert "entries" in result


def test_list_catalog_shows_seed_flags():
    result = run(ft.list_flag_catalog())
    assert "disableMinify" in result


def test_list_catalog_filter_works():
    result = run(ft.list_flag_catalog("minify"))
    assert "disableMinify" in result
    assert "forceUncompressedTextures" not in result


def test_list_catalog_filter_no_match():
    result = run(ft.list_flag_catalog("zzznomatch"))
    assert "no entries match" in result


def test_list_catalog_degraded():
    ft._catalog = None
    result = run(ft.list_flag_catalog())
    assert "[DEGRADED" in result


# --- lookup_flag ---

def test_lookup_flag_found():
    result = run(ft.lookup_flag("disableMinify"))
    assert "disableMinify" in result
    assert "risk=" in result
    assert "description:" in result


def test_lookup_flag_missing():
    result = run(ft.lookup_flag("nope"))
    assert "[INVALID" in result


def test_lookup_flag_degraded():
    ft._catalog = None
    result = run(ft.lookup_flag("disableMinify"))
    assert "[DEGRADED" in result


def test_lookup_flag_shows_side_effects():
    result = run(ft.lookup_flag("disableMinify"))
    assert "side_effects:" in result


def test_lookup_flag_shows_build_size():
    result = run(ft.lookup_flag("disableMinify"))
    assert "build_size_delta:" in result


# --- recommend_flags ---

def test_recommend_flags_finds_match():
    result = run(ft.recommend_flags("disable minification"))
    assert "disableMinify" in result


def test_recommend_flags_no_match():
    result = run(ft.recommend_flags("xyzzy foobarbaz"))
    assert "no flags match" in result


def test_recommend_flags_degraded():
    ft._recommender = None
    result = run(ft.recommend_flags("anything"))
    assert "[DEGRADED" in result


def test_recommend_flags_shows_risk():
    result = run(ft.recommend_flags("disable minification"))
    assert "low" in result or "medium" in result or "high" in result
