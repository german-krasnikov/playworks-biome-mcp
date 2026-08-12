"""Tests for Jakefile MCP tools — RED phase."""
import pathlib
from unittest.mock import MagicMock

import pytest

from luna_mcp.tools.jakefile_tools import (
    _make_analyze_jakefile,
    _make_apply_jakefile_patch,
    _make_revert_jakefile_patch,
    _make_suggest_jakefile_patch,
    register_jakefile_tools,
)

SAMPLE_JAKE = """\
// Line 1
// Line 2
// Line 3
// Line 4
// Line 5
// Line 6 version meta
task('build', function() {});
var quality_setting = {quality: 85};
var jpeg_marker = 'jpeg_compression_string';
"""


def make_jakefile(tmp_path, content=SAMPLE_JAKE):
    j = tmp_path / "Jakefile.js"
    j.write_text(content)
    return j


# --- analyze_jakefile ---

@pytest.mark.asyncio
async def test_analyze_returns_summary(tmp_path, monkeypatch):
    make_jakefile(tmp_path)
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(tmp_path / "Jakefile.js"))
    fn = _make_analyze_jakefile()
    result = await fn()
    assert "path=" in result
    assert "version_sha=" in result
    assert "tasks=" in result


@pytest.mark.asyncio
async def test_analyze_not_found(monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    monkeypatch.chdir("/tmp")
    fn = _make_analyze_jakefile()
    result = await fn()
    assert "[INVALID" in result or "not found" in result.lower()


# --- suggest_jakefile_patch ---

@pytest.mark.asyncio
async def test_suggest_no_file(monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    monkeypatch.chdir("/tmp")
    fn = _make_suggest_jakefile_patch(planner=None)
    result = await fn(intent="reduce size")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_suggest_no_planner(tmp_path, monkeypatch):
    make_jakefile(tmp_path)
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(tmp_path / "Jakefile.js"))
    fn = _make_suggest_jakefile_patch(planner=None)
    result = await fn(intent="reduce size")
    assert "DEGRADED" in result or "PLANNER_UNAVAILABLE" in result


@pytest.mark.asyncio
async def test_suggest_with_dsl(tmp_path, monkeypatch):
    make_jakefile(tmp_path)
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(tmp_path / "Jakefile.js"))

    class FakePlanner:
        async def plan(self, intent, index, ctx=""):
            return "PATCH id=x search=quality: 85 replace=quality: 65 count=1"

    fn = _make_suggest_jakefile_patch(planner=FakePlanner())
    result = await fn(intent="lower quality")
    assert "PLAN:" in result
    assert "VALIDATION:" in result


# --- apply_jakefile_patch (dry_run=True) ---

@pytest.mark.asyncio
async def test_apply_dry_run_known_template(tmp_path, monkeypatch):
    # Create a jakefile that matches the lower_jpeg_quality template's search
    j = tmp_path / "Jakefile.js"
    j.write_text("// L1\n// L2\n// L3\n// L4\n// L5\n// L6\njpeg x;\nvar cfg = {quality: 85};\n")
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(j))
    fn = _make_apply_jakefile_patch(shadow_base=tmp_path / "shadow")
    result = await fn(template_name="lower_jpeg_quality", dry_run=True)
    assert "DRY_RUN" in result or "lower_jpeg_quality" in result


@pytest.mark.asyncio
async def test_apply_unknown_template(tmp_path, monkeypatch):
    j = tmp_path / "Jakefile.js"
    j.write_text("// stub")
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(j))
    fn = _make_apply_jakefile_patch(shadow_base=tmp_path / "shadow")
    result = await fn(template_name="nonexistent_template", dry_run=True)
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_apply_no_file(monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    monkeypatch.chdir("/tmp")
    fn = _make_apply_jakefile_patch(shadow_base=pathlib.Path("/tmp/shadow"))
    result = await fn(template_name="lower_jpeg_quality", dry_run=True)
    assert "[INVALID" in result


# --- revert_jakefile_patch ---

@pytest.mark.asyncio
async def test_revert_not_in_history(tmp_path, monkeypatch):
    from luna_mcp.build_intel.store import PatchStore
    store = PatchStore(tmp_path / "patches.db")
    fn = _make_revert_jakefile_patch(store=store, shadow_base=tmp_path / "shadow")
    result = await fn(patch_id="nonexistent_patch_id")
    assert "[INVALID" in result


# --- M1: double-revert returns friendly error ---

@pytest.mark.asyncio
async def test_double_revert_returns_already_reverted(tmp_path, monkeypatch):
    from luna_mcp.build_intel.store import PatchStore
    store = PatchStore(tmp_path / "patches.db")
    # Insert a record with status='reverted' directly
    store.record("some_patch", "intent", str(tmp_path / "Jakefile.js"), "deadbeef")
    store.update_status("some_patch", "reverted")
    fn = _make_revert_jakefile_patch(store=store, shadow_base=tmp_path / "shadow")
    result = await fn(patch_id="some_patch")
    assert "already reverted" in result.lower()
    assert "[INVALID" in result


# --- M3: apply → revert full cycle ---

@pytest.mark.asyncio
async def test_apply_then_revert_full_cycle(tmp_path, monkeypatch):
    from luna_mcp.build_intel.store import PatchStore
    j = tmp_path / "Jakefile.js"
    # lower_jpeg_quality: anchor_before='jpeg', search='quality: 85', within 300 chars
    j.write_text("// header\n// l2\n// l3\n// l4\n// l5\n// l6\nvar config = { jpeg: { quality: 85 } };")
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(j))

    shadow = tmp_path / "shadow"
    store = PatchStore(tmp_path / "patches.db")

    apply_fn = _make_apply_jakefile_patch(shadow_base=shadow, store=store)
    result = await apply_fn(template_name="lower_jpeg_quality", dry_run=False)
    assert "applied" in result.lower(), f"apply failed: {result}"
    assert "quality: 65" in j.read_text()

    revert_fn = _make_revert_jakefile_patch(store=store, shadow_base=shadow)
    result = await revert_fn(patch_id="lower_jpeg_quality")
    assert "reverted" in result.lower(), f"revert failed: {result}"
    assert "quality: 85" in j.read_text()
    assert "quality: 65" not in j.read_text()


# --- register_jakefile_tools ---

def test_register_returns_dict():
    mcp_mock = MagicMock()
    result = register_jakefile_tools(mcp_mock, planner=None, shadow_base=pathlib.Path("/tmp"))
    assert "analyze_jakefile" in result
    assert "suggest_jakefile_patch" in result
    assert "apply_jakefile_patch" in result
    assert "revert_jakefile_patch" in result


def test_register_returns_tuple_format():
    mcp_mock = MagicMock()
    result = register_jakefile_tools(mcp_mock, planner=None, shadow_base=pathlib.Path("/tmp"))
    for name, val in result.items():
        fn, params = val
        assert callable(fn)
        # params is None (sentinel) or explicit dict — both resolve to dict via derive_params
        assert params is None or isinstance(params, dict)
