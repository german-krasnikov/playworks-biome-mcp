"""TDD tests for regression/store.py — BaselineStore + get_build_hash."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def store(tmp_path):
    from luna_mcp.regression.store import BaselineStore
    return BaselineStore(root=tmp_path / "baselines")


@pytest.fixture
def png_bytes():
    # Minimal valid-ish PNG bytes
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


# 1
async def test_save_creates_files(store, png_bytes):
    path = await store.save("abc123", "main", png_bytes)
    assert path.exists()
    assert path.suffix == ".png"
    meta = store.root / "abc123" / "main.json"
    assert meta.exists()


# 2
async def test_load_returns_path_and_meta(store, png_bytes):
    await store.save("abc123", "main", png_bytes, mask_zones="0,0,10,10", semantic_hint="check header")
    result = store.load("abc123", "main")
    assert result is not None
    png_path, meta = result
    assert png_path.exists()
    assert meta["mask_zones"] == "0,0,10,10"
    assert meta["semantic_hint"] == "check header"


# 3
def test_load_missing_returns_none(store):
    assert store.load("nonexistent", "whatever") is None


# 4
async def test_save_atomic_uses_tmp_rename(store, png_bytes):
    replaced = []
    orig_replace = __import__("os").replace

    def track_replace(src, dst):
        replaced.append((src, dst))
        return orig_replace(src, dst)

    with patch("os.replace", side_effect=track_replace):
        await store.save("abc", "shot", png_bytes)

    assert len(replaced) == 1
    src, dst = replaced[0]
    assert ".png.tmp" in src
    assert dst.endswith("shot.png")


# 5
async def test_invalidate_one(store, png_bytes):
    await store.save("abc", "shot1", png_bytes)
    await store.save("abc", "shot2", png_bytes)
    count = store.invalidate("abc", name="shot1")
    assert count == 2  # png + json
    assert store.load("abc", "shot1") is None
    assert store.load("abc", "shot2") is not None


# 6
async def test_invalidate_all_for_build(store, png_bytes):
    await store.save("abc", "s1", png_bytes)
    await store.save("abc", "s2", png_bytes)
    count = store.invalidate("abc")
    assert count == 4  # 2 png + 2 json
    assert store.list("abc") == []


# 7
async def test_list_returns_names_sorted(store, png_bytes):
    await store.save("abc", "zebra", png_bytes)
    await store.save("abc", "apple", png_bytes)
    await store.save("abc", "mango", png_bytes)
    names = store.list("abc")
    assert names == ["apple", "mango", "zebra"]


# 8
async def test_concurrent_save_lock(store, png_bytes):
    """Four concurrent saves for different names don't corrupt each other."""
    tasks = [
        store.save("abc", f"shot{i}", png_bytes)
        for i in range(4)
    ]
    await asyncio.gather(*tasks)
    names = store.list("abc")
    assert sorted(names) == ["shot0", "shot1", "shot2", "shot3"]


# 9
async def test_get_build_hash_uses_luna_build_id():
    from luna_mcp.regression.store import get_build_hash
    bridge = MagicMock()
    bridge.eval = AsyncMock(return_value="build-xyz-1.0")
    h = await get_build_hash(bridge)
    assert isinstance(h, str)
    assert len(h) == 16


# 10
async def test_get_build_hash_fallback_script_srcs():
    from luna_mcp.regression.store import get_build_hash
    bridge = MagicMock()
    # First call returns empty (no __luna_build_id), second returns script srcs
    bridge.eval = AsyncMock(side_effect=["", "app.js|vendor.js"])
    h = await get_build_hash(bridge)
    assert isinstance(h, str)
    assert len(h) == 16


async def test_get_build_hash_fallback_on_exception():
    from luna_mcp.regression.store import get_build_hash
    bridge = MagicMock()
    bridge.eval = AsyncMock(side_effect=Exception("no chrome"))
    h = await get_build_hash(bridge)
    assert h == "default"


async def test_save_stores_pixel_threshold(store, png_bytes):
    await store.save("abc", "main", png_bytes, pixel_threshold=2.5)
    _, meta = store.load("abc", "main")
    assert meta["pixel_threshold"] == 2.5


async def test_save_stores_created_at(store, png_bytes):
    before = time.time()
    await store.save("abc", "main", png_bytes)
    after = time.time()
    _, meta = store.load("abc", "main")
    assert before <= meta["created_at"] <= after


def test_list_empty_for_unknown_build(store):
    assert store.list("unknown_build_xyz") == []
