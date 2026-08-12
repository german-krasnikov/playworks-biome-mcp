"""RED: FlagCatalog — JSON-based persistent catalog."""
import json

import pytest

from luna_mcp.flag_explorer.catalog import FlagCatalog, FlagEntry


@pytest.fixture
def catalog(tmp_path):
    return FlagCatalog(tmp_path / "flags.json")


def test_catalog_empty_on_init(catalog):
    assert catalog.all() == []


def test_catalog_add_and_get(catalog):
    e = FlagEntry(name="myFlag", description="Test flag")
    catalog.add(e)
    got = catalog.get("myFlag")
    assert got is not None
    assert got.name == "myFlag"
    assert got.description == "Test flag"


def test_catalog_get_missing_returns_none(catalog):
    assert catalog.get("nonexistent") is None


def test_catalog_all_sorted(catalog):
    catalog.add(FlagEntry(name="zzz", description="z"))
    catalog.add(FlagEntry(name="aaa", description="a"))
    names = [e.name for e in catalog.all()]
    assert names == sorted(names)


def test_catalog_save_and_reload(tmp_path):
    path = tmp_path / "flags.json"
    c1 = FlagCatalog(path)
    c1.add(FlagEntry(name="testFlag", description="desc", risk="low"))
    c1.save()
    assert path.exists()
    c2 = FlagCatalog(path)
    e = c2.get("testFlag")
    assert e is not None
    assert e.risk == "low"


def test_catalog_save_is_atomic(tmp_path):
    path = tmp_path / "flags.json"
    c = FlagCatalog(path)
    c.add(FlagEntry(name="f", description="d"))
    c.save()
    # no .tmp file left behind
    assert not (tmp_path / "flags.tmp").exists()


def test_catalog_json_format(tmp_path):
    path = tmp_path / "flags.json"
    c = FlagCatalog(path)
    c.add(FlagEntry(name="f", description="d"))
    c.save()
    data = json.loads(path.read_text())
    assert "version" in data
    assert "flags" in data
    assert data["flags"][0]["name"] == "f"


def test_catalog_entry_defaults(catalog):
    e = FlagEntry(name="x", description="y")
    catalog.add(e)
    got = catalog.get("x")
    assert got.risk == "unknown"
    assert got.confidence == 0.5
    assert got.source == "user"
    assert got.side_effects == []


def test_catalog_add_updates_last_updated(catalog):
    e = FlagEntry(name="f", description="d")
    catalog.add(e)
    assert catalog.get("f").last_updated > 0


def test_catalog_add_overwrites_existing(catalog):
    catalog.add(FlagEntry(name="f", description="old"))
    catalog.add(FlagEntry(name="f", description="new"))
    assert catalog.get("f").description == "new"


def test_catalog_find_by_intent_returns_matches(catalog):
    catalog.add(FlagEntry(name="disableMinify", description="Disable JS minification", enables="readable names"))
    catalog.add(FlagEntry(name="compressTextures", description="Compress textures"))
    results = catalog.find_by_intent(["minify"])
    assert any(e.name == "disableMinify" for e in results)


def test_catalog_find_by_intent_no_match_returns_empty(catalog):
    catalog.add(FlagEntry(name="f", description="something"))
    results = catalog.find_by_intent(["zzznomatch"])
    assert results == []


def test_catalog_find_by_intent_ranks_by_score(catalog):
    catalog.add(FlagEntry(name="a", description="minify size compression"))
    catalog.add(FlagEntry(name="b", description="minify only"))
    results = catalog.find_by_intent(["minify", "size", "compression"])
    assert results[0].name == "a"


def test_catalog_load_bad_json_silently_ignored(tmp_path):
    path = tmp_path / "flags.json"
    path.write_text("NOTJSON{{{")
    c = FlagCatalog(path)
    assert c.all() == []


def test_catalog_side_effects_roundtrip(tmp_path):
    path = tmp_path / "flags.json"
    c1 = FlagCatalog(path)
    c1.add(FlagEntry(name="f", description="d", side_effects=["a", "b"]))
    c1.save()
    c2 = FlagCatalog(path)
    assert c2.get("f").side_effects == ["a", "b"]


def test_load_skips_corrupt_entry_keeps_others(tmp_path):
    """M1: corrupt entry mid-list must not kill subsequent valid entries."""
    path = tmp_path / "flags.json"
    data = {
        "version": 1,
        "flags": [
            {"name": "validFirst", "description": "first"},
            {"description": "missing_name_field"},   # corrupt — no 'name'
            {"name": "validLast", "description": "last"},
        ],
    }
    path.write_text(json.dumps(data))
    c = FlagCatalog(path)
    names = {e.name for e in c.all()}
    assert names == {"validFirst", "validLast"}
