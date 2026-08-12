"""Tests for build_diff/router.py — RED phase."""
import pathlib

import pytest

from luna_mcp.build_diff.indexer import BuildIndex
from luna_mcp.build_diff.router import TierRouter
from luna_mcp.build_diff.semantic_diff import SemanticDiff


def _scan(root, label, files):
    root = pathlib.Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (root / name).write_text(content)
    return BuildIndex.scan(root, label)


class _MockSampling:
    enabled = True
    async def plan(self, prompt, system):
        return "semantic summary"


class _DisabledSampling:
    enabled = False
    async def plan(self, prompt, system):
        raise AssertionError("should not call")


async def _no_visual(pa, pb):
    return None


@pytest.mark.asyncio
async def test_router_file_mode_no_semantic(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"main.js": "old"})
    b = _scan(tmp_path / "b", "v2", {"main.js": "new"})
    sd = SemanticDiff(_DisabledSampling())
    router = TierRouter(sd, _no_visual)
    result = await router.diff(a, b, mode="file")
    assert "v1" in result and "v2" in result
    assert "semantic" not in result


@pytest.mark.asyncio
async def test_router_auto_mode_includes_header(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"main.js": "old"})
    b = _scan(tmp_path / "b", "v2", {"main.js": "new"})
    router = TierRouter(SemanticDiff(None), _no_visual)
    result = await router.diff(a, b, mode="auto")
    assert "build_diff" in result
    assert "v1" in result
    assert "v2" in result


@pytest.mark.asyncio
async def test_router_semantic_mode_calls_haiku(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"main.js": "old code"})
    b = _scan(tmp_path / "b", "v2", {"main.js": "new code"})
    mock = _MockSampling()
    router = TierRouter(SemanticDiff(mock), _no_visual)
    result = await router.diff(a, b, mode="semantic")
    assert "semantic" in result
    assert "semantic summary" in result or "main.js" in result


@pytest.mark.asyncio
async def test_router_semantic_caps_at_5_files(tmp_path):
    """Router must not call Haiku for more than 5 modified text files."""
    files = {f"f{i}.js": f"old{i}" for i in range(10)}
    a = _scan(tmp_path / "a", "v1", files)
    files_b = {f"f{i}.js": f"new{i}" for i in range(10)}
    b = _scan(tmp_path / "b", "v2", files_b)

    call_count = 0
    class _CountingSampling:
        enabled = True
        async def plan(self, p, s):
            nonlocal call_count
            call_count += 1
            return "summary"

    router = TierRouter(SemanticDiff(_CountingSampling()), _no_visual)
    await router.diff(a, b, mode="semantic")
    assert call_count <= 5


@pytest.mark.asyncio
async def test_router_visual_mode_reports_png_diff(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"sprite.png": "data"})
    b = _scan(tmp_path / "b", "v2", {"sprite.png": "other"})

    async def _visual(pa, pb):
        return 12.5  # 12.5% pixel diff

    router = TierRouter(SemanticDiff(None), _visual)
    result = await router.diff(a, b, mode="visual")
    assert "visual" in result
    assert "sprite.png" in result
    assert "12.5" in result


@pytest.mark.asyncio
async def test_router_visual_skips_low_diff(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"sprite.png": "data"})
    b = _scan(tmp_path / "b", "v2", {"sprite.png": "other"})

    async def _visual(pa, pb):
        return 0.1  # below 0.5% threshold

    router = TierRouter(SemanticDiff(None), _visual)
    result = await router.diff(a, b, mode="visual")
    assert "sprite.png" not in result or "0.1" not in result


@pytest.mark.asyncio
async def test_router_unchanged_no_output(tmp_path):
    a = _scan(tmp_path / "a", "v1", {"same.js": "same"})
    b = _scan(tmp_path / "b", "v2", {"same.js": "same"})
    router = TierRouter(SemanticDiff(None), _no_visual)
    result = await router.diff(a, b, mode="auto")
    assert "same.js" not in result  # unchanged file not reported


@pytest.mark.asyncio
async def test_router_file_mode_returns_summary_line(tmp_path):
    a_dir = tmp_path / "a"; a_dir.mkdir()
    a = BuildIndex.scan(a_dir, "v1")
    b = _scan(tmp_path / "b", "v2", {"new.js": "hello"})
    router = TierRouter(SemanticDiff(None), _no_visual)
    result = await router.diff(a, b, mode="file")
    assert "size delta" in result
    assert "+1" in result or "added" in result or "new.js" in result


# --- M1: router handles async visual_fn correctly ---

@pytest.mark.asyncio
async def test_router_handles_async_visual_fn(tmp_path):
    """PNG change in auto mode with async visual_fn — no TypeError, visual section appears."""
    a = _scan(tmp_path / "a", "v1", {"sprite.png": "old"})
    b = _scan(tmp_path / "b", "v2", {"sprite.png": "new"})

    async def async_visual(pa, pb):
        return 15.0

    router = TierRouter(SemanticDiff(None), async_visual)
    result = await router.diff(a, b, mode="auto")
    assert "visual" in result
    assert "sprite.png" in result


# --- m5: _TEXT_KINDS imported from indexer (not duplicated) ---

def test_router_text_kinds_same_as_indexer():
    from luna_mcp.build_diff.indexer import _TEXT_KINDS as indexer_kinds
    from luna_mcp.build_diff.router import _TEXT_KINDS as router_kinds
    assert router_kinds == indexer_kinds
