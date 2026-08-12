"""Tests for physics MCP tools."""

import pytest

from luna_mcp.lessons.store import LessonStore
from luna_mcp.physics_detective.seeds import seed_physics_lessons

# --- detect_physics_backend ---

@pytest.mark.asyncio
async def test_detect_backend_no_physics():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=false verlet=false baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.detect()
    assert "no physics detected" in result


@pytest.mark.asyncio
async def test_detect_backend_goblin():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=true verlet=false baked=false unified=false goblin.bodies=3 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.detect()
    assert "goblin" in result
    assert "goblin.bodies=3" in result


# --- diagnose_physics ---

@pytest.mark.asyncio
async def test_diagnose_no_physics():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=false verlet=false baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.diagnose("object shaking")
    assert "no physics detected" in result


@pytest.mark.asyncio
async def test_diagnose_with_lesson(tmp_path):
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    store = LessonStore(tmp_path / "l.db")
    seed_physics_lessons(store)

    async def call_fn(method, *args):
        return "goblin=true verlet=false baked=false unified=false goblin.bodies=5 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, store)
    result = await diag.diagnose("object is jiggling and shaking")
    assert "[goblin]" in result
    store.close()


@pytest.mark.asyncio
async def test_diagnose_no_lesson_match(tmp_path):
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    store = LessonStore(tmp_path / "l.db")
    seed_physics_lessons(store)

    async def call_fn(method, *args):
        return "goblin=true verlet=false baked=false unified=false goblin.bodies=1 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, store)
    result = await diag.diagnose("completely unrelated symptom xyz abc")
    assert "No matching lessons" in result
    store.close()


# --- physics_health_check ---

@pytest.mark.asyncio
async def test_health_check_no_physics():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=false verlet=false baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.health_check()
    assert "OK" in result


@pytest.mark.asyncio
async def test_health_check_multiple_backends_warns():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=true verlet=true baked=false unified=false goblin.bodies=2 verlet.particles=5 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.health_check()
    assert "WARNING" in result
    assert "multiple backends" in result


@pytest.mark.asyncio
async def test_health_check_many_goblin_bodies_warns():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=true verlet=false baked=false unified=false goblin.bodies=60 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.health_check()
    assert "60" in result
    assert "INFO" in result


@pytest.mark.asyncio
async def test_health_check_many_verlet_particles_warns():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=false verlet=true baked=false unified=false goblin.bodies=0 verlet.particles=250 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.health_check()
    assert "250" in result
    assert "INFO" in result


@pytest.mark.asyncio
async def test_health_check_ok_single_backend():
    from luna_mcp.physics_detective.diagnose_flow import PhysicsDiagnostic

    async def call_fn(method, *args):
        return "goblin=true verlet=false baked=false unified=false goblin.bodies=3 verlet.particles=0 baked.entries=0"

    diag = PhysicsDiagnostic(call_fn, None, None)
    result = await diag.health_check()
    assert result.startswith("OK")


# --- tools module ---

def test_physics_tools_returns_4_entries():
    from luna_mcp.tools.physics_tools import register_physics_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_physics_tools(FakeMCP(), None, None, None)
    assert len(tools) == 4
    assert "detect_physics_backend" in tools
    assert "diagnose_physics" in tools
    assert "physics_health_check" in tools
    assert "compare_physics_states" in tools


@pytest.mark.asyncio
async def test_degraded_when_not_initialized():
    from luna_mcp.tools.physics_tools import register_physics_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_physics_tools(FakeMCP(), None, None, None)
    detect_fn, _ = tools["detect_physics_backend"]
    result = await detect_fn()
    assert "[DEGRADED" in result


@pytest.mark.asyncio
async def test_diagnose_tool_degraded_no_init():
    from luna_mcp.tools.physics_tools import register_physics_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_physics_tools(FakeMCP(), None, None, None)
    fn, _ = tools["diagnose_physics"]
    result = await fn(symptom="shaking")
    assert "[DEGRADED" in result


# m6: compare_physics_states degraded when _compare_states_fn is None
@pytest.mark.asyncio
async def test_compare_physics_states_degraded_when_no_fn():
    import luna_mcp.tools.physics_tools as pt
    orig = pt._compare_states_fn
    pt._compare_states_fn = None
    try:
        result = await pt.compare_physics_states("a", "b")
        assert "[DEGRADED:physics:" in result
    finally:
        pt._compare_states_fn = orig
