"""Tests for TemplateRegistry."""
import time

import pytest

from luna_mcp.templates.registry import TemplateRegistry


@pytest.fixture
def bundled_dir(tmp_path):
    d = tmp_path / "bundled"
    d.mkdir()
    return d


@pytest.fixture
def user_dir(tmp_path):
    d = tmp_path / "user"
    d.mkdir()
    return d


@pytest.fixture
def registry(bundled_dir, user_dir):
    return TemplateRegistry(bundled_dir=bundled_dir, user_dir=user_dir)


def make_template(dir, name, body):
    p = dir / f"{name}.batch"
    p.write_text(body)
    return p


def test_load_bundled_template(registry, bundled_dir):
    make_template(bundled_dir, "check_btn", "# params: path\nget_object_detail path={{path}}")
    t = registry.load("check_btn")
    assert t is not None
    assert t.name == "check_btn"
    assert "get_object_detail" in t.body
    assert "path" in t.params


def test_user_overrides_bundled(registry, bundled_dir, user_dir):
    make_template(bundled_dir, "foo", "bundled body")
    make_template(user_dir, "foo", "user body")
    t = registry.load("foo")
    assert t.body == "user body"


def test_load_returns_none_for_missing(registry):
    assert registry.load("nonexistent") is None


def test_mtime_cache_invalidation(registry, bundled_dir):
    p = make_template(bundled_dir, "cached", "v1")
    t1 = registry.load("cached")
    assert t1.body == "v1"
    # overwrite with slightly newer mtime
    time.sleep(0.05)
    p.write_text("v2")
    t2 = registry.load("cached")
    assert t2.body == "v2"


def test_cache_hit_returns_same_object(registry, bundled_dir):
    make_template(bundled_dir, "stable", "body")
    t1 = registry.load("stable")
    t2 = registry.load("stable")
    assert t1 is t2


def test_list_all_includes_user_and_bundled(registry, bundled_dir, user_dir):
    make_template(bundled_dir, "a", "body a")
    make_template(user_dir, "b", "body b")
    names = {t.name for t in registry.list_all()}
    assert "a" in names
    assert "b" in names


def test_list_all_user_deduplicates_bundled(registry, bundled_dir, user_dir):
    make_template(bundled_dir, "dup", "bundled")
    make_template(user_dir, "dup", "user")
    items = registry.list_all()
    dups = [t for t in items if t.name == "dup"]
    assert len(dups) == 1
    assert dups[0].body == "user"


def test_list_all_filter(registry, bundled_dir):
    make_template(bundled_dir, "check_install", "body")
    make_template(bundled_dir, "diagnose_endcard", "body")
    results = registry.list_all("check")
    assert all("check" in t.name for t in results)
    assert len(results) == 1


def test_save_user_creates_file(registry, user_dir):
    p = registry.save_user("my_tpl", "get_hierarchy")
    assert p.exists()
    assert p.read_text() == "get_hierarchy"


def test_save_user_invalid_name_raises(registry):
    with pytest.raises(ValueError, match="invalid template name"):
        registry.save_user("has space!", "body")


def test_save_user_existing_no_overwrite_raises(registry, user_dir):
    make_template(user_dir, "existing", "old")
    with pytest.raises(FileExistsError):
        registry.save_user("existing", "new")


def test_save_user_overwrite_works(registry, user_dir):
    make_template(user_dir, "existing", "old")
    registry.save_user("existing", "new", overwrite=True)
    assert (user_dir / "existing.batch").read_text() == "new"


def test_template_parses_header_meta(registry, bundled_dir):
    body = "# params: path,count\n# desc: my description\n# version: 2\nget_hierarchy"
    make_template(bundled_dir, "meta_test", body)
    t = registry.load("meta_test")
    assert t.params == ["path", "count"]
    assert t.desc == "my description"
    assert t.version == "2"


def test_template_no_header(registry, bundled_dir):
    make_template(bundled_dir, "plain", "get_hierarchy depth=2")
    t = registry.load("plain")
    assert t.params == []
    assert t.desc == ""
    assert t.version == "1"


def test_bundled_dir_resolves_to_package_dir():
    """C2: bundled templates must live inside the Python package."""
    from luna_mcp.templates.registry import _BUNDLED_DIR
    assert _BUNDLED_DIR.exists(), f"_BUNDLED_DIR does not exist: {_BUNDLED_DIR}"
    batch_files = list(_BUNDLED_DIR.glob("*.batch"))
    assert len(batch_files) == 5, f"expected 5 bundled templates, got {len(batch_files)}: {batch_files}"
