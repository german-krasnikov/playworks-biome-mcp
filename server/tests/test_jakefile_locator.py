"""Tests for Jakefile locator — RED phase."""
from luna_mcp.build_intel.locator import find_jakefile


def test_finds_via_env(tmp_path, monkeypatch):
    j = tmp_path / "Jakefile.js"
    j.write_text("// stub")
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(j))
    assert find_jakefile() == j


def test_env_nonexistent_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(tmp_path / "missing.js"))
    assert find_jakefile() is None


def test_env_directory_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(tmp_path))
    assert find_jakefile() is None


def test_returns_none_when_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert find_jakefile() is None


def test_finds_in_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    j = tmp_path / "Jakefile.js"
    j.write_text("// stub")
    monkeypatch.chdir(tmp_path)
    assert find_jakefile() == j


def test_finds_in_parent(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_JAKEFILE_PATH", raising=False)
    j = tmp_path / "Jakefile.js"
    j.write_text("// stub")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    assert find_jakefile() == j


def test_env_expanded(tmp_path, monkeypatch):
    """Env path with ~ expansion."""
    j = tmp_path / "Jakefile.js"
    j.write_text("// stub")
    monkeypatch.setenv("LUNA_JAKEFILE_PATH", str(j))
    result = find_jakefile()
    assert result is not None
    assert result.exists()
