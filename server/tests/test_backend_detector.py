"""Tests for BackendInfo parser and detect_backend."""
import pytest

from luna_mcp.physics_detective.backend_detector import BackendInfo


def test_parses_goblin_only():
    info = BackendInfo("goblin=true verlet=false baked=false unified=false goblin.bodies=12 verlet.particles=0 baked.entries=0")
    assert info.goblin is True
    assert info.verlet is False
    assert info.baked is False
    assert info.unified is False
    assert info.goblin_bodies == 12
    assert info.verlet_particles == 0
    assert info.baked_entries == 0
    assert info.active_backends() == ["goblin"]


def test_parses_verlet_only():
    info = BackendInfo("goblin=false verlet=true baked=false unified=false goblin.bodies=0 verlet.particles=35 baked.entries=0")
    assert info.verlet is True
    assert info.goblin is False
    assert info.verlet_particles == 35
    assert info.active_backends() == ["verlet"]


def test_parses_baked_only():
    info = BackendInfo("goblin=false verlet=false baked=true unified=false goblin.bodies=0 verlet.particles=0 baked.entries=7")
    assert info.baked is True
    assert info.baked_entries == 7
    assert info.active_backends() == ["baked"]


def test_parses_unified_only():
    info = BackendInfo("goblin=false verlet=false baked=false unified=true goblin.bodies=0 verlet.particles=0 baked.entries=0")
    assert info.unified is True
    assert info.active_backends() == ["unified"]


def test_multiple_backends():
    info = BackendInfo("goblin=true verlet=true baked=false unified=false goblin.bodies=5 verlet.particles=20 baked.entries=0")
    assert info.active_backends() == ["goblin", "verlet"]
    assert info.goblin_bodies == 5
    assert info.verlet_particles == 20


def test_no_physics():
    info = BackendInfo("goblin=false verlet=false baked=false unified=false goblin.bodies=0 verlet.particles=0 baked.entries=0")
    assert info.active_backends() == []
    assert info.summary() == "no physics detected"


def test_summary_goblin():
    info = BackendInfo("goblin=true verlet=false baked=false unified=false goblin.bodies=12 verlet.particles=0 baked.entries=0")
    s = info.summary()
    assert "backends=goblin" in s
    assert "goblin.bodies=12" in s


def test_summary_multiple():
    info = BackendInfo("goblin=true verlet=true baked=false unified=false goblin.bodies=3 verlet.particles=15 baked.entries=0")
    s = info.summary()
    assert "goblin" in s
    assert "verlet" in s
    assert "goblin.bodies=3" in s
    assert "verlet.particles=15" in s


def test_error_raw():
    info = BackendInfo("error: some exception")
    assert info.active_backends() == []
    assert info.goblin_bodies == 0


@pytest.mark.asyncio
async def test_detect_backend_returns_backend_info():
    from luna_mcp.physics_detective.backend_detector import detect_backend
    raw = "goblin=true verlet=false baked=false unified=false goblin.bodies=5 verlet.particles=0 baked.entries=0"

    async def mock_call(method, *args):
        return raw

    info = await detect_backend(mock_call)
    assert info.goblin is True
    assert info.goblin_bodies == 5


@pytest.mark.asyncio
async def test_detect_backend_handles_exception():
    from luna_mcp.physics_detective.backend_detector import detect_backend

    async def bad_call(method, *args):
        raise RuntimeError("CDP down")

    info = await detect_backend(bad_call)
    assert info.active_backends() == []
