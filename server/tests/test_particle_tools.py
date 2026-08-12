"""Tests for F5 audit_particles tool."""
import pathlib

import pytest

JS_PATH = pathlib.Path(__file__).parent.parent.parent / "js" / "luna_helpers.js"


class FakeMCP:
    def tool(self, **kw):
        def dec(fn): return fn
        return dec


# --- tool registration ---

def test_particle_tools_returns_1_entry():
    from luna_mcp.tools.particle_tools import register_particle_tools
    tools = register_particle_tools(FakeMCP(), None, exposed=set())
    assert len(tools) == 1
    assert "audit_particles" in tools


# --- passthrough tests ---

@pytest.mark.asyncio
async def test_audit_passes_particleAudit():
    from luna_mcp.tools.particle_tools import register_particle_tools
    calls = []

    async def fake_call(method, *args):
        calls.append(method)
        return "no particle systems found"

    tools = register_particle_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["audit_particles"]
    await fn()
    assert calls == ["particleAudit"]


@pytest.mark.asyncio
async def test_audit_passthrough_no_systems():
    from luna_mcp.tools.particle_tools import register_particle_tools

    async def fake_call(method, *args):
        return "no particle systems found"

    tools = register_particle_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["audit_particles"]
    result = await fn()
    assert result == "no particle systems found"


@pytest.mark.asyncio
async def test_audit_passthrough_formats():
    from luna_mcp.tools.particle_tools import register_particle_tools

    rows = (
        "Canvas/Particles | 50/200 play=True emit=True rate=10 t=1.23\n"
        "Canvas/Smoke | 5/100 play=True emit=False rate=2 t=0.50"
    )

    async def fake_call(method, *args):
        return rows

    tools = register_particle_tools(FakeMCP(), fake_call, exposed=set())
    fn, _ = tools["audit_particles"]
    result = await fn()
    assert result == rows


# --- JS-presence ---

def test_particle_audit_js_present():
    js = JS_PATH.read_text()
    assert 'particleAudit' in js
    assert 'rateOverTime' in js
    assert '.constant' in js
