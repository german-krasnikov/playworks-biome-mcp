"""Tests for build_id module."""
import os

import pytest

from luna_mcp.build_id import get_build_hash, reset_cache


@pytest.fixture(autouse=True)
def clear_cache():
    reset_cache()
    yield
    reset_cache()


class FakeBridge:
    def __init__(self, return_val=""):
        self._val = return_val
        self.calls = []

    async def eval(self, expr):
        self.calls.append(expr)
        return self._val


@pytest.mark.asyncio
async def test_uses_lunabuildid_first():
    bridge = FakeBridge("build_v1.2.3")
    result = await get_build_hash(bridge)
    assert result != "default"
    assert len(result) == 12


@pytest.mark.asyncio
async def test_cached_after_first_call():
    bridge = FakeBridge("build_v1.2.3")
    r1 = await get_build_hash(bridge)
    r2 = await get_build_hash(bridge)
    assert r1 == r2
    # Second call should not re-eval
    assert len(bridge.calls) == 1


@pytest.mark.asyncio
async def test_falls_back_to_plugin_mtime(tmp_path):
    plugin = tmp_path / "plugin.js"
    plugin.write_text("fake plugin content")
    os.environ["LUNA_PLUGIN_PATH"] = str(plugin)
    bridge = FakeBridge("")  # no __luna_build_id
    try:
        result = await get_build_hash(bridge)
        assert result != "default"
        assert len(result) == 12
    finally:
        del os.environ["LUNA_PLUGIN_PATH"]


@pytest.mark.asyncio
async def test_falls_back_to_scripts():
    os.environ.pop("LUNA_PLUGIN_PATH", None)

    class ScriptsBridge:
        call_count = 0
        async def eval(self, expr):
            self.call_count += 1
            if "luna_build_id" in expr:
                return ""
            # scripts fallback
            return "app.js|game.js|bundle.js"

    bridge = ScriptsBridge()
    result = await get_build_hash(bridge)
    assert result != "default"
    assert len(result) == 12


@pytest.mark.asyncio
async def test_default_when_all_fail():
    class FailBridge:
        async def eval(self, expr):
            raise RuntimeError("no connection")

    os.environ.pop("LUNA_PLUGIN_PATH", None)
    bridge = FailBridge()
    result = await get_build_hash(bridge)
    assert result == "default"


@pytest.mark.asyncio
async def test_reset_cache_clears():
    bridge = FakeBridge("v1")
    await get_build_hash(bridge)
    reset_cache()
    bridge2 = FakeBridge("v2")
    r2 = await get_build_hash(bridge2)
    assert r2 != "default"
    assert len(bridge2.calls) == 1
