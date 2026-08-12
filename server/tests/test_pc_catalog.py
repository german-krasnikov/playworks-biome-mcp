"""Tests for pc_replacer.catalog — RED phase."""
import json

import pytest

from luna_mcp.pc_replacer.catalog import ModuleCatalog


def make_json(tmp_path, modules):
    data = tmp_path / "pc_modules.json"
    data.write_text(json.dumps({"version": 1, "modules": modules}))
    return data


def test_load_single_module(tmp_path):
    data = make_json(tmp_path, [
        {"id": "particle-system", "exports": ["pc.ParticleSystemSystem"], "size_kb": 107, "category": "rendering"}
    ])
    cat = ModuleCatalog(data)
    assert len(cat.all()) == 1
    m = cat.all()[0]
    assert m.id == "particle-system"
    assert m.size_kb == 107
    assert m.category == "rendering"
    assert "pc.ParticleSystemSystem" in m.exports


def test_load_multiple_modules(tmp_path):
    data = make_json(tmp_path, [
        {"id": "a", "exports": ["pc.A"], "size_kb": 10, "category": "foo"},
        {"id": "b", "exports": ["pc.B"], "size_kb": 20, "category": "bar"},
    ])
    cat = ModuleCatalog(data)
    assert len(cat.all()) == 2


def test_get_by_id(tmp_path):
    data = make_json(tmp_path, [
        {"id": "audio", "exports": ["pc.SoundComponent"], "size_kb": 30, "category": "audio"}
    ])
    cat = ModuleCatalog(data)
    m = cat.get("audio")
    assert m is not None
    assert m.id == "audio"


def test_get_missing_returns_none(tmp_path):
    data = make_json(tmp_path, [])
    cat = ModuleCatalog(data)
    assert cat.get("nonexistent") is None


def test_missing_file_returns_empty(tmp_path):
    cat = ModuleCatalog(tmp_path / "nonexistent.json")
    assert cat.all() == []


def test_corrupted_json_returns_empty(tmp_path):
    data = tmp_path / "bad.json"
    data.write_text("{not valid json}")
    cat = ModuleCatalog(data)
    assert cat.all() == []


def test_missing_key_skips_module(tmp_path):
    # module missing 'exports' key — should be skipped (KeyError)
    data = tmp_path / "partial.json"
    data.write_text(json.dumps({"version": 1, "modules": [{"id": "bad_no_exports", "size_kb": 10}]}))
    cat = ModuleCatalog(data)
    assert cat.all() == []


def test_total_kb(tmp_path):
    data = make_json(tmp_path, [
        {"id": "a", "exports": ["pc.A"], "size_kb": 50, "category": "x"},
        {"id": "b", "exports": ["pc.B"], "size_kb": 30, "category": "y"},
    ])
    cat = ModuleCatalog(data)
    assert cat.total_kb() == 80


def test_default_category(tmp_path):
    data = tmp_path / "no_cat.json"
    data.write_text(json.dumps({"version": 1, "modules": [
        {"id": "x", "exports": ["pc.X"], "size_kb": 10}
    ]}))
    cat = ModuleCatalog(data)
    assert cat.all()[0].category == "other"


def test_module_info_is_frozen(tmp_path):
    data = make_json(tmp_path, [
        {"id": "x", "exports": ["pc.X"], "size_kb": 10, "category": "foo"}
    ])
    cat = ModuleCatalog(data)
    m = cat.all()[0]
    with pytest.raises(Exception):
        m.id = "changed"  # frozen dataclass
