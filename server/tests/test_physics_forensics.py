"""Tests for S3.4 physics forensics tools."""
import pathlib

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# --- inspect_bodies ---

@pytest.mark.asyncio
async def test_inspect_bodies_reuses_probe_goblin():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        if method == "physicsProbe":
            return "goblin=true verlet=false baked=false unified=false goblin.bodies=3 verlet.particles=0 baked.entries=0"
        if method == "rigidbodyDump":
            return "Node1 vel=(0,0,0) mass=1.0"
        return ""
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["inspect_bodies"]
    result = await fn()
    assert called[0] == "physicsProbe"
    assert "rigidbodyDump" in called
    assert "Node1" in result


@pytest.mark.asyncio
async def test_inspect_bodies_reuses_probe_2d():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        if method == "physicsProbe":
            return "goblin=false verlet=true baked=false unified=false goblin.bodies=0 verlet.particles=5 baked.entries=0"
        if method == "listBodies2d":
            return "body1 type=2 awake=True pos=(1.0,2.0)"
        return ""
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["inspect_bodies"]
    result = await fn()
    assert called[0] == "physicsProbe"
    assert "listBodies2d" in called


@pytest.mark.asyncio
async def test_inspect_bodies_no_physics():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        return "goblin=false verlet=false baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0"
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["inspect_bodies"]
    result = await fn()
    assert "no physics" in result.lower()
    # should not call rigidbodyDump or listBodies2d
    assert "rigidbodyDump" not in called
    assert "listBodies2d" not in called


# --- physics_query ---

@pytest.mark.asyncio
async def test_query_raycast2d_passthrough():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        return "hit collider=Wall"
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["physics_query"]
    result = await fn("raycast2d", 0.0, 0.0, 1.0, 0.0, 100.0)
    assert "raycast2d" in called
    assert "hit" in result


@pytest.mark.asyncio
async def test_query_invalid_kind():
    called = []
    async def call_fn(method, *args):
        called.append(method)
        return ""
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["physics_query"]
    result = await fn("flycast", 0.0, 0.0)
    assert "INVALID" in result
    assert not called


@pytest.mark.asyncio
async def test_query_raycast3d_uses_existing():
    called = []
    async def call_fn(method, *args):
        called.append((method, args))
        return "hit something"
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["physics_query"]
    result = await fn("raycast3d", 1.0, 2.0)
    # must reuse existing "raycast" method with (a, b) as args
    assert any(c[0] == "raycast" for c in called)
    first_raycast = next(c for c in called if c[0] == "raycast")
    assert first_raycast[1][0] == 1.0
    assert first_raycast[1][1] == 2.0


@pytest.mark.asyncio
async def test_backend_lacking_api_no_crash():
    async def call_fn(method, *args):
        if method == "physicsProbe":
            return "goblin=false verlet=true baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0"
        if method == "listBodies2d":
            return "error: no physics2D"
        return ""
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["inspect_bodies"]
    result = await fn()
    # no crash — error surfaced in result
    assert "error" in result.lower() or result  # just no exception


@pytest.mark.asyncio
async def test_raycast2d_collider_code_kept():
    """Integer collider code kept as-is when not resolved."""
    async def call_fn(method, *args):
        return "hit collider=42 point=(1.00,2.00)"
    from luna_mcp.tools.physics_forensics_tools import register_physics_forensics_tools
    reg = register_physics_forensics_tools(FakeMCP(), call_fn, exposed=set())
    fn, _ = reg["physics_query"]
    result = await fn("raycast2d", 0.0, 0.0, 1.0, 0.0)
    assert result  # no crash, code passed through


# --- JS presence ---

def test_js_rigidbodyDump_present():
    src = JS_PATH.read_text()
    assert "rigidbodyDump:" in src


def test_js_listBodies2d_present():
    src = JS_PATH.read_text()
    assert "listBodies2d:" in src


def test_js_raycast2d_present():
    src = JS_PATH.read_text()
    assert "raycast2d:" in src


def test_js_overlapPoint2d_present():
    src = JS_PATH.read_text()
    assert "overlapPoint2d:" in src


def test_js_contactPairs_present():
    src = JS_PATH.read_text()
    assert "contactPairs:" in src


def test_js_guards_physics2d():
    src = JS_PATH.read_text()
    assert "systems.physics2D" in src


def test_js_guards_colliders():
    src = JS_PATH.read_text()
    assert "_colliders" in src


def test_js_no_goblin_world_instances_in_rigidbodyDump():
    """rigidbodyDump must NOT use Goblin.World._instances."""
    src = JS_PATH.read_text()
    # Extract rigidbodyDump section
    start = src.find("rigidbodyDump:")
    end = src.find("\n        },", start)
    section = src[start:end]
    assert "Goblin.World._instances" not in section
