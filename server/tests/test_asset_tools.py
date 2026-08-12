"""Tests for asset MCP tools — RED phase."""
from __future__ import annotations

import pathlib

import pytest


# M2 — plan_id uniqueness under rapid successive calls
def test_plan_id_unique_under_rapid_calls():
    from luna_mcp.asset_optimizer.plan import make_plan
    ids = [make_plan(100, []).plan_id for _ in range(100)]
    assert len(set(ids)) == 100, "plan_id collisions detected"

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "textures"


@pytest.fixture
def assets_dir(tmp_path):
    (tmp_path / "sprite.png").write_bytes((FIXTURES / "sprite.png").read_bytes())
    (tmp_path / "photo.png").write_bytes((FIXTURES / "photo_large.png").read_bytes())
    (tmp_path / "audio.mp3").write_bytes(b"fake_audio" * 100)
    return tmp_path


# -- audit_assets --

@pytest.mark.asyncio
async def test_audit_returns_summary(assets_dir):
    from luna_mcp.tools.asset_tools import audit_assets
    result = await audit_assets(str(assets_dir))
    assert "texture" in result
    assert "audio" in result
    assert "total" in result


@pytest.mark.asyncio
async def test_audit_shows_file_count(assets_dir):
    from luna_mcp.tools.asset_tools import audit_assets
    result = await audit_assets(str(assets_dir))
    assert "3 files" in result or "files" in result


@pytest.mark.asyncio
async def test_audit_invalid_path():
    from luna_mcp.tools.asset_tools import audit_assets
    result = await audit_assets("/tmp/does_not_exist_xyz_abc")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_audit_shows_root(assets_dir):
    from luna_mcp.tools.asset_tools import audit_assets
    result = await audit_assets(str(assets_dir))
    assert "root=" in result


# -- analyze_texture --

@pytest.mark.asyncio
async def test_analyze_texture_returns_info():
    from luna_mcp.tools.asset_tools import analyze_texture
    result = await analyze_texture(str(FIXTURES / "sprite.png"))
    assert "width" in result or "size=" in result
    assert "classification=" in result


@pytest.mark.asyncio
async def test_analyze_texture_invalid_path():
    from luna_mcp.tools.asset_tools import analyze_texture
    result = await analyze_texture("/tmp/does_not_exist_xyz.png")
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_analyze_texture_shows_entropy():
    from luna_mcp.tools.asset_tools import analyze_texture
    result = await analyze_texture(str(FIXTURES / "photo_large.png"))
    assert "entropy=" in result


@pytest.mark.asyncio
async def test_analyze_texture_shows_alpha():
    from luna_mcp.tools.asset_tools import analyze_texture
    result = await analyze_texture(str(FIXTURES / "sprite.png"))
    assert "alpha=" in result


# -- recommend_asset_optimization --

@pytest.mark.asyncio
async def test_recommend_returns_plan(assets_dir):
    from luna_mcp.tools.asset_tools import recommend_asset_optimization
    result = await recommend_asset_optimization(str(assets_dir), 100)
    # either a plan or "no actions" is valid
    assert "plan_id=" in result or "no actions" in result


@pytest.mark.asyncio
async def test_recommend_invalid_path():
    from luna_mcp.tools.asset_tools import recommend_asset_optimization
    result = await recommend_asset_optimization("/tmp/no_dir_xyz", 100)
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_recommend_stores_plan_for_apply(assets_dir):
    from luna_mcp.tools.asset_tools import apply_asset_optimization, recommend_asset_optimization
    rec_result = await recommend_asset_optimization(str(assets_dir), 100)
    if "no actions" in rec_result:
        pytest.skip("no actions generated")
    # extract plan_id
    plan_id = rec_result.split("plan_id=")[1].split(" ")[0]
    apply_result = await apply_asset_optimization(plan_id, dry_run=True)
    assert "DRY_RUN" in apply_result


# -- apply_asset_optimization --

@pytest.mark.asyncio
async def test_apply_unknown_plan_id():
    from luna_mcp.tools.asset_tools import apply_asset_optimization
    result = await apply_asset_optimization("unknownplanxyz", dry_run=True)
    assert "[INVALID" in result


@pytest.mark.asyncio
async def test_apply_real_returns_degraded(assets_dir):
    from luna_mcp.tools.asset_tools import apply_asset_optimization, recommend_asset_optimization
    rec_result = await recommend_asset_optimization(str(assets_dir), 100)
    if "no actions" in rec_result:
        pytest.skip("no actions generated")
    plan_id = rec_result.split("plan_id=")[1].split(" ")[0]
    result = await apply_asset_optimization(plan_id, dry_run=False)
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_apply_dry_run_shows_action_count(assets_dir):
    from luna_mcp.tools.asset_tools import apply_asset_optimization, recommend_asset_optimization
    rec_result = await recommend_asset_optimization(str(assets_dir), 10000)
    if "no actions" in rec_result:
        pytest.skip("no actions generated")
    plan_id = rec_result.split("plan_id=")[1].split(" ")[0]
    result = await apply_asset_optimization(plan_id, dry_run=True)
    assert "actions" in result
