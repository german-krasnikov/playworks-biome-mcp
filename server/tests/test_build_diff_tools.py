"""Tests for tools/build_diff_tools.py — RED phase."""
import pytest


async def _noop_visual(a, b):
    return None


def _make_tool_env(tmp_path):
    """Create fresh tool module state for isolation."""
    from luna_mcp.build_diff.router import TierRouter
    from luna_mcp.build_diff.semantic_diff import SemanticDiff
    from luna_mcp.build_diff.storage import BuildStore

    store = BuildStore(tmp_path / "store")
    router = TierRouter(SemanticDiff(None), _noop_visual)
    return store, router


@pytest.fixture()
def tools(tmp_path):
    """Returns (index_build, diff_builds, list_builds, bisect_change) with isolated store."""
    from luna_mcp.build_diff.router import TierRouter
    from luna_mcp.build_diff.semantic_diff import SemanticDiff
    from luna_mcp.build_diff.storage import BuildStore

    store = BuildStore(tmp_path / "store")
    router = TierRouter(SemanticDiff(None), _noop_visual)

    from luna_mcp.tools.build_diff_tools import (
        _make_bisect_change,
        _make_diff_builds,
        _make_index_build,
        _make_list_builds,
    )
    return (
        _make_index_build(store),
        _make_diff_builds(store, router),
        _make_list_builds(store),
        _make_bisect_change(store),
    )


@pytest.mark.asyncio
async def test_index_build_success(tmp_path, tools):
    index_build, *_ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "main.js").write_text("hello")
    result = await index_build(str(bdir), "v1.0")
    assert "indexed" in result
    assert "v1.0" in result
    assert "1 files" in result or "files" in result


@pytest.mark.asyncio
async def test_index_build_invalid_label(tmp_path, tools):
    index_build, *_ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    result = await index_build(str(bdir), "INVALID LABEL!")
    assert result.startswith("[INVALID")


@pytest.mark.asyncio
async def test_index_build_nonexistent_path(tmp_path, tools):
    index_build, *_ = tools
    result = await index_build(str(tmp_path / "nope"), "v1")
    assert result.startswith("[INVALID")


@pytest.mark.asyncio
async def test_index_build_label_dot_ok(tmp_path, tools):
    index_build, *_ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    result = await index_build(str(bdir), "v1.0.0")
    assert "indexed" in result


@pytest.mark.asyncio
async def test_index_build_persists(tmp_path, tools):
    index_build, _, list_builds, _ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    await index_build(str(bdir), "v1")
    listed = await list_builds()
    assert "v1" in listed


@pytest.mark.asyncio
async def test_diff_builds_unknown_label_a(tmp_path, tools):
    _, diff_builds, _, _ = tools
    result = await diff_builds("missing_a", "missing_b")
    assert "[INVALID" in result or "not indexed" in result


@pytest.mark.asyncio
async def test_diff_builds_unknown_label_b(tmp_path, tools):
    index_build, diff_builds, _, _ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    await index_build(str(bdir), "v1")
    result = await diff_builds("v1", "v99")
    assert "[INVALID" in result or "not indexed" in result


@pytest.mark.asyncio
async def test_diff_builds_returns_diff(tmp_path, tools):
    index_build, diff_builds, _, _ = tools
    a_dir = tmp_path / "a"; a_dir.mkdir()
    b_dir = tmp_path / "b"; b_dir.mkdir()
    (a_dir / "main.js").write_text("old")
    (b_dir / "main.js").write_text("new")
    await index_build(str(a_dir), "v1")
    await index_build(str(b_dir), "v2")
    result = await diff_builds("v1", "v2")
    assert "v1" in result and "v2" in result
    assert "main.js" in result


@pytest.mark.asyncio
async def test_list_builds_empty(tmp_path, tools):
    _, _, list_builds, _ = tools
    result = await list_builds()
    assert "no builds" in result


@pytest.mark.asyncio
async def test_list_builds_shows_label(tmp_path, tools):
    index_build, _, list_builds, _ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    await index_build(str(bdir), "release.1")
    result = await list_builds()
    assert "release.1" in result


@pytest.mark.asyncio
async def test_bisect_change_no_intermediates(tmp_path, tools):
    index_build, _, _, bisect_change = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    await index_build(str(bdir), "good")
    await index_build(str(bdir), "bad")
    result = await bisect_change("good", "bad", "")
    assert "culprit" in result
    assert "bad" in result


@pytest.mark.asyncio
async def test_bisect_change_missing_label_handled(tmp_path, tools):
    _, _, _, bisect_change = tools
    result = await bisect_change("missing_good", "missing_bad", "")
    # Should not crash — return some message
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_register_build_diff_tools_returns_dict():
    """register_build_diff_tools returns {name: (fn, params)}."""
    from luna_mcp.tools.build_diff_tools import register_build_diff_tools

    class _MockMcp:
        def tool(self, **kw):
            def deco(fn):
                return fn
            return deco

    result = register_build_diff_tools(_MockMcp(), None, None)
    assert isinstance(result, dict)
    assert "index_build" in result
    assert "diff_builds" in result
    assert "list_builds" in result
    assert "bisect_change" in result

    # Each value is (callable, params_dict_or_None)
    for name, (fn, params) in result.items():
        assert callable(fn)
        assert params is None or isinstance(params, dict)


# --- M4: bisect caches good_label outside probe ---

@pytest.mark.asyncio
async def test_bisect_returns_invalid_for_missing_good(tmp_path, tools):
    _, _, _, bisect_change = tools
    result = await bisect_change("nonexistent_good", "nonexistent_bad", "")
    assert "INVALID" in result
    assert "nonexistent_good" in result


@pytest.mark.asyncio
async def test_bisect_result_includes_criterion(tmp_path, tools):
    index_build, _, _, bisect_change = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    await index_build(str(bdir), "good")
    await index_build(str(bdir), "bad")
    result = await bisect_change("good", "bad", "")
    assert "criterion" in result or "culprit" in result


# --- m6: label rejects backslash ---

@pytest.mark.asyncio
async def test_index_build_rejects_backslash_in_label(tmp_path, tools):
    index_build, *_ = tools
    bdir = tmp_path / "build"; bdir.mkdir()
    (bdir / "x.js").write_text("x")
    result = await index_build(str(bdir), r"v1\bad")
    assert result.startswith("[INVALID")
