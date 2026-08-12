"""Tests for pc_replacer MCP tools — RED phase."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from luna_mcp.pc_replacer.catalog import ModuleInfo
from luna_mcp.tools.pc_replacer_tools import (
    _make_apply_pc_replacement,
    _make_audit_pc_modules,
    _make_recommend_pc_replacements,
    _make_revert_pc_replacement,
    _make_validate_pc_replacement,
    register_pc_replacer_tools,
)


def make_catalog(entries=None):
    if entries is None:
        entries = [("particle", ["pc.ParticleSystemSystem"], 107, "rendering")]
    mods = {e[0]: ModuleInfo(id=e[0], exports=e[1], size_kb=e[2], category=e[3]) for e in entries}

    class _Cat:
        def all(self):
            return list(mods.values())
        def get(self, mid):
            return mods.get(mid)

    return _Cat()


def make_scan_result(items=None):
    if items is None:
        items = [("particle", "unused", 107, "no probes")]
    return {i[0]: {"usage": i[1], "size_kb": i[2], "evidence": i[3]} for i in items}


# --- audit_pc_modules ---

@pytest.mark.asyncio
async def test_audit_not_initialized():
    fn = _make_audit_pc_modules(None)
    result = await fn()
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_audit_returns_table():
    cat = make_catalog()
    scan = make_scan_result()

    async def fake_scan():
        return scan

    scanner = MagicMock()
    scanner.scan = AsyncMock(return_value=scan)
    fn = _make_audit_pc_modules(scanner)
    result = await fn()
    assert "particle" in result
    assert "unused" in result
    assert "107" in result


@pytest.mark.asyncio
async def test_audit_empty_scan():
    scanner = MagicMock()
    scanner.scan = AsyncMock(return_value={})
    fn = _make_audit_pc_modules(scanner)
    result = await fn()
    assert "no modules" in result


# --- recommend_pc_replacements ---

@pytest.mark.asyncio
async def test_recommend_not_initialized():
    fn = _make_recommend_pc_replacements(None, None)
    result = await fn(100)
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_recommend_calls_recommender():
    scan = make_scan_result()
    scanner = MagicMock()
    scanner.scan = AsyncMock(return_value=scan)
    recommender = MagicMock()
    recommender.recommend = AsyncMock(return_value="target_save_kb=100 achievable_kb=107\n  particle -> stub")
    fn = _make_recommend_pc_replacements(scanner, recommender)
    result = await fn(100)
    assert "particle" in result


# --- apply_pc_replacement ---

@pytest.mark.asyncio
async def test_apply_not_initialized():
    fn = _make_apply_pc_replacement(None, None)
    result = await fn("particle")
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_apply_dry_run_default():
    cat = make_catalog()
    applier = MagicMock()
    applier.stub_module = AsyncMock(return_value="stubbed: particle")
    fn = _make_apply_pc_replacement(applier, cat)
    result = await fn("particle")
    # dry_run=True by default
    assert "DRY_RUN" in result
    applier.stub_module.assert_not_called()


@pytest.mark.asyncio
async def test_apply_wet_run():
    cat = make_catalog()
    applier = MagicMock()
    applier.stub_module = AsyncMock(return_value="stubbed: particle (2 exports backed up)")
    fn = _make_apply_pc_replacement(applier, cat)
    result = await fn("particle", dry_run=False)
    assert "stubbed" in result
    applier.stub_module.assert_called_once()


@pytest.mark.asyncio
async def test_apply_unknown_module():
    cat = make_catalog()
    applier = MagicMock()
    fn = _make_apply_pc_replacement(applier, cat)
    result = await fn("nonexistent", dry_run=False)
    assert "[INVALID" in result


# --- validate_pc_replacement ---

@pytest.mark.asyncio
async def test_validate_not_initialized():
    fn = _make_validate_pc_replacement(None)
    result = await fn("baseline")
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_validate_pass():
    from luna_mcp.pc_replacer.validator import Validator

    async def fake_check(name):
        return "PASS pixel pct=0.00"

    v = Validator(fake_check)
    fn = _make_validate_pc_replacement(v)
    result = await fn("test-baseline")
    assert "PASS" in result


@pytest.mark.asyncio
async def test_validate_fail():
    from luna_mcp.pc_replacer.validator import Validator

    async def fake_check(name):
        return "DIFF pixel pct=5.00"

    v = Validator(fake_check)
    fn = _make_validate_pc_replacement(v)
    result = await fn("test-baseline")
    assert "FAIL" in result


# --- revert_pc_replacement ---

@pytest.mark.asyncio
async def test_revert_not_initialized():
    fn = _make_revert_pc_replacement(None, None)
    result = await fn("particle")
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_revert_calls_applier():
    cat = make_catalog()
    applier = MagicMock()
    applier.revert_module = AsyncMock(return_value="reverted: particle")
    fn = _make_revert_pc_replacement(applier, cat)
    result = await fn("particle")
    assert "reverted" in result
    applier.revert_module.assert_called_once()


@pytest.mark.asyncio
async def test_revert_unknown_module():
    cat = make_catalog()
    applier = MagicMock()
    fn = _make_revert_pc_replacement(applier, cat)
    result = await fn("nonexistent")
    assert "[INVALID" in result


# --- register_pc_replacer_tools ---

def test_register_returns_all_5_tools():
    from unittest.mock import MagicMock
    mcp = MagicMock()
    cat = make_catalog()
    scanner = MagicMock()
    recommender = MagicMock()
    applier = MagicMock()

    from luna_mcp.pc_replacer.validator import Validator
    async def fake_check(name): return "PASS"
    validator = Validator(fake_check)

    result = register_pc_replacer_tools(
        mcp, catalog=cat, scanner=scanner,
        recommender=recommender, applier=applier,
        validator=validator, exposed=set()
    )
    assert set(result.keys()) == {
        "audit_pc_modules",
        "recommend_pc_replacements",
        "apply_pc_replacement",
        "validate_pc_replacement",
        "revert_pc_replacement",
    }
