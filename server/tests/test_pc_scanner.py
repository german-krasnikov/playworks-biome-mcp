"""Tests for pc_replacer.scanner — RED phase."""
import pytest

from luna_mcp.pc_replacer.catalog import ModuleInfo
from luna_mcp.pc_replacer.scanner import UsageScanner


def make_catalog(entries):
    """entries: list of (id, exports, size_kb)"""
    mods = [ModuleInfo(id=e[0], exports=e[1], size_kb=e[2], category="test") for e in entries]

    class _Cat:
        def all(self):
            return mods
        def get(self, mid):
            return next((m for m in mods if m.id == mid), None)

    return _Cat()


@pytest.mark.asyncio
async def test_scan_classifies_unused():
    cat = make_catalog([("particle", ["pc.ParticleSystemSystem"], 100)])

    async def fake_eval(expr):
        return "false"  # nothing defined

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["particle"]["usage"] == "unused"
    assert result["particle"]["size_kb"] == 100


@pytest.mark.asyncio
async def test_scan_classifies_partial_when_defined_no_instances():
    cat = make_catalog([("audio", ["pc.SoundComponent"], 30)])
    call_log = []

    async def fake_eval(expr):
        call_log.append(expr)
        if "typeof" in expr:
            return "true"  # defined
        return "-1"  # no component count (returns -1)

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["audio"]["usage"] == "partial"


@pytest.mark.asyncio
async def test_scan_classifies_used_when_components_present():
    cat = make_catalog([("ui-2d", ["pc.ElementComponent"], 45)])

    async def fake_eval(expr):
        if "typeof" in expr:
            return "true"
        return "5"  # 5 instances

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["ui-2d"]["usage"] == "used"


@pytest.mark.asyncio
async def test_scan_multiple_modules():
    cat = make_catalog([
        ("particle", ["pc.ParticleSystemSystem"], 100),
        ("audio", ["pc.SoundComponent"], 30),
    ])

    async def fake_eval(expr):
        if "typeof" in expr and "Sound" in expr:
            return "true"
        return "false"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert "particle" in result
    assert "audio" in result


@pytest.mark.asyncio
async def test_scan_eval_exception_treats_as_undefined():
    cat = make_catalog([("particle", ["pc.ParticleSystemSystem"], 100)])

    async def bad_eval(expr):
        raise RuntimeError("CDP error")

    scanner = UsageScanner(cat, bad_eval)
    result = await scanner.scan()
    assert result["particle"]["usage"] == "unused"


@pytest.mark.asyncio
async def test_scan_evidence_recorded():
    cat = make_catalog([("audio", ["pc.SoundComponent"], 30)])

    async def fake_eval(expr):
        if "typeof" in expr:
            return "true"
        return "3"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["audio"]["evidence"] != ""
    assert "defined" in result["audio"]["evidence"]


@pytest.mark.asyncio
async def test_scan_empty_catalog():
    cat = make_catalog([])

    async def fake_eval(expr):
        return "false"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result == {}


@pytest.mark.asyncio
async def test_scan_non_component_export_no_instance_check():
    """Non-Component exports (no 'Component' in name) skip count check — stay partial."""
    cat = make_catalog([("anim", ["pc.AnimStateGraph"], 65)])
    eval_calls = []

    async def fake_eval(expr):
        eval_calls.append(expr)
        if "typeof" in expr:
            return "true"
        return "0"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    # AnimStateGraph not a Component — should be partial (defined but no instance check)
    assert result["anim"]["usage"] == "partial"


@pytest.mark.asyncio
async def test_scanner_uses_app_systems_store_for_component_count():
    """M3: component count check must use app.systems[name].store, not findComponentsByType."""
    cat = make_catalog([("audio", ["pc.SoundComponent"], 30)])
    eval_calls = []

    async def fake_eval(expr):
        eval_calls.append(expr)
        if "typeof" in expr:
            return "true"
        return "3"  # count from systems.store

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()

    # Must have called eval for the component count
    component_count_calls = [e for e in eval_calls if "typeof" not in e]
    assert len(component_count_calls) >= 1
    count_expr = component_count_calls[0]
    # Should use app.systems store, NOT findComponentsByType
    assert "app.systems" in count_expr
    assert "findComponentsByType" not in count_expr


# ---- A2: physics3d real export names -----------------------------------------

@pytest.mark.asyncio
async def test_physics3d_used_when_rigidbody_present():
    """A2: RigidbodyComponent (lowercase b) probe → usage == 'used'."""
    cat = make_catalog([("physics3d", [
        "pc.RigidbodyComponent", "pc.ColliderComponent",
        "pc.BoxColliderComponent", "pc.CapsuleColliderComponent",
        "pc.SphereColliderComponent", "pc.MeshColliderComponent",
        "pc.WheelColliderComponent", "pc.CharacterControllerComponent",
        "pc.JointComponent",
    ], 80)])

    async def fake_eval(expr):
        if "typeof" in expr and "Rigidbody" in expr:
            return "true"
        if "typeof" in expr:
            return "false"
        if "'rigidbody'" in expr:
            return "4"
        return "-1"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["physics3d"]["usage"] == "used"


@pytest.mark.asyncio
async def test_physics3d_collider_present_classifies_used():
    """A2: ColliderComponent probe → usage == 'used'."""
    cat = make_catalog([("physics3d", [
        "pc.RigidbodyComponent", "pc.ColliderComponent",
    ], 80)])

    async def fake_eval(expr):
        if "typeof" in expr and "Collider" in expr:
            return "true"
        if "typeof" in expr:
            return "false"
        if "'collider'" in expr:
            return "3"
        return "-1"

    scanner = UsageScanner(cat, fake_eval)
    result = await scanner.scan()
    assert result["physics3d"]["usage"] == "used"


def test_physics3d_catalog_has_no_fake_names():
    """A2: shipped catalog must use real names, not RigidBodyComponent/CollisionComponent."""
    import json
    import pathlib
    data_path = pathlib.Path(__file__).parent.parent / "src/luna_mcp/pc_replacer/data/pc_modules.json"
    data = json.loads(data_path.read_text())
    p3d = next(m for m in data["modules"] if m["id"] == "physics3d")
    exports = p3d["exports"]
    # real names must be present
    assert "pc.RigidbodyComponent" in exports
    assert "pc.ColliderComponent" in exports
    # fake names must be gone
    assert "pc.RigidBodyComponent" not in exports
    assert "pc.CollisionComponent" not in exports
