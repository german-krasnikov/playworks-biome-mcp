"""Tests for luna_config tools — config.json get/set/diff + jake driver."""
from __future__ import annotations

import json
import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Config locator tests
# ---------------------------------------------------------------------------

def test_find_config_via_env(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high"}')
    from luna_mcp.luna_config.locator import find_config
    with patch.dict(os.environ, {"LUNA_PLUGIN_PATH": str(tmp_path)}):
        result = find_config()
    assert result == cfg


def test_find_config_scan_cwd(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "low"}')
    from luna_mcp.luna_config.locator import find_config
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = find_config()
    assert result == cfg


def test_find_config_missing_returns_none(tmp_path):
    from luna_mcp.luna_config.locator import find_config
    with patch.dict(os.environ, {"LUNA_PLUGIN_PATH": str(tmp_path)}):
        result = find_config()
    assert result is None


def test_find_config_env_path_is_file(tmp_path):
    """LUNA_PLUGIN_PATH may point directly to config.json."""
    cfg = tmp_path / "config.json"
    cfg.write_text('{}')
    from luna_mcp.luna_config.locator import find_config
    with patch.dict(os.environ, {"LUNA_PLUGIN_PATH": str(cfg)}):
        result = find_config()
    assert result == cfg


# ---------------------------------------------------------------------------
# Config reader tests
# ---------------------------------------------------------------------------

def test_config_reader_get(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high", "size": 512}')
    from luna_mcp.luna_config.reader import read_config
    data = read_config(cfg)
    assert data["quality"] == "high"
    assert data["size"] == 512


def test_config_reader_invalid_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("not json {{")
    from luna_mcp.luna_config.reader import read_config
    with pytest.raises(ValueError, match="invalid JSON"):
        read_config(cfg)


# ---------------------------------------------------------------------------
# Config writer tests (atomic write + backup)
# ---------------------------------------------------------------------------

def test_config_writer_atomic_write(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high"}')
    from luna_mcp.luna_config.writer import write_config
    write_config(cfg, {"quality": "ultra", "new_key": True})
    data = json.loads(cfg.read_text())
    assert data["quality"] == "ultra"
    assert data["new_key"] is True


def test_config_writer_creates_backup(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high"}')
    from luna_mcp.luna_config.writer import write_config
    write_config(cfg, {"quality": "ultra"})
    backup = cfg.with_suffix(".json.bak")
    assert backup.exists()
    original = json.loads(backup.read_text())
    assert original["quality"] == "high"


def test_config_writer_revert_from_backup(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high"}')
    from luna_mcp.luna_config.writer import revert_config, write_config
    write_config(cfg, {"quality": "ultra"})
    revert_config(cfg)
    data = json.loads(cfg.read_text())
    assert data["quality"] == "high"


def test_config_writer_revert_no_backup(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{}')
    from luna_mcp.luna_config.writer import revert_config
    with pytest.raises(FileNotFoundError, match="backup"):
        revert_config(cfg)


def test_config_writer_validates_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{}')
    from luna_mcp.luna_config.writer import write_config
    # Must reject non-dict
    with pytest.raises(TypeError):
        write_config(cfg, ["not", "a", "dict"])  # type: ignore


def test_config_writer_no_mktemp(tmp_path):
    """write_config must NOT use tempfile.mktemp (TOCTOU race). Verify via source."""
    import inspect

    from luna_mcp.luna_config import writer
    src = inspect.getsource(writer)
    assert "mktemp(" not in src, "mktemp() is TOCTOU-unsafe; use NamedTemporaryFile"


def test_config_writer_cleans_up_tmp_on_error(tmp_path):
    """On write failure no .tmp file should survive in parent dir."""
    cfg = tmp_path / "config.json"
    cfg.write_text('{}')
    from luna_mcp.luna_config.writer import write_config
    # Patch replace to fail after write
    original_replace = pathlib.Path.replace

    def boom(self, target):
        raise OSError("disk full")

    with patch.object(pathlib.Path, "replace", boom):
        with pytest.raises(OSError):
            write_config(cfg, {"k": "v"})
    leftover = list(tmp_path.glob(".cfg_*.tmp"))
    assert leftover == [], f"temp file not cleaned up: {leftover}"


# ---------------------------------------------------------------------------
# Config diff tests
# ---------------------------------------------------------------------------

def test_config_diff_added_removed_changed(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"keep": 1, "remove": 2, "change": "old"}')
    b.write_text('{"keep": 1, "add": 3, "change": "new"}')
    from luna_mcp.luna_config.differ import diff_configs
    result = diff_configs(a, b)
    assert "add" in result
    assert "remove" in result
    assert "change" in result


def test_config_diff_identical(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text('{"x": 1}')
    b.write_text('{"x": 1}')
    from luna_mcp.luna_config.differ import diff_configs
    result = diff_configs(a, b)
    assert "identical" in result.lower() or result.strip() == "" or "no diff" in result.lower()


# ---------------------------------------------------------------------------
# MCP Tool function tests
# ---------------------------------------------------------------------------

def test_luna_config_get_tool(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high", "target": "webgl"}')
    from luna_mcp.tools.luna_config_tools import luna_config_get
    with patch("luna_mcp.tools.luna_config_tools.find_config", return_value=cfg):
        import asyncio
        result = asyncio.run(luna_config_get())
    assert "quality" in result
    assert "high" in result


def test_luna_config_get_no_config(tmp_path):
    from luna_mcp.tools.luna_config_tools import luna_config_get
    with patch("luna_mcp.tools.luna_config_tools.find_config", return_value=None):
        import asyncio
        result = asyncio.run(luna_config_get())
    assert "INVALID" in result or "not found" in result.lower()


def test_luna_config_set_tool(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"quality": "high"}')
    from luna_mcp.tools.luna_config_tools import luna_config_set
    with patch("luna_mcp.tools.luna_config_tools.find_config", return_value=cfg):
        import asyncio
        result = asyncio.run(luna_config_set('{"quality": "ultra"}'))
    assert "ok" in result.lower() or "written" in result.lower() or "success" in result.lower()
    data = json.loads(cfg.read_text())
    assert data["quality"] == "ultra"


def test_luna_config_set_invalid_json(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{}')
    from luna_mcp.tools.luna_config_tools import luna_config_set
    with patch("luna_mcp.tools.luna_config_tools.find_config", return_value=cfg):
        import asyncio
        result = asyncio.run(luna_config_set("not json"))
    assert "INVALID" in result


def test_luna_config_diff_tool(tmp_path):
    cfg_a = tmp_path / "a.json"
    cfg_b = tmp_path / "b.json"
    cfg_a.write_text('{"quality": "high"}')
    cfg_b.write_text('{"quality": "ultra"}')
    import asyncio

    from luna_mcp.tools.luna_config_tools import luna_config_diff
    result = asyncio.run(luna_config_diff(str(cfg_a), str(cfg_b)))
    assert "quality" in result


# ---------------------------------------------------------------------------
# Jake driver tests
# ---------------------------------------------------------------------------

def test_jake_driver_dry_run(tmp_path):
    from luna_mcp.luna_config.jake_driver import JakeDriver
    driver = JakeDriver(project_path=str(tmp_path))
    result = driver.build(dry_run=True)
    assert result["dry_run"] is True
    assert "jake" in result["command"].lower() or "node" in result["command"].lower() or "./jake" in result["command"]
    assert result.get("executed") is False


def test_jake_driver_validates_project_path(tmp_path):
    from luna_mcp.luna_config.jake_driver import JakeDriver
    driver = JakeDriver(project_path=str(tmp_path / "nonexistent"))
    result = driver.build(dry_run=True)
    assert "error" in result or result.get("valid") is False


def test_jake_driver_execute_mocked(tmp_path):
    """execute=True should call subprocess; mock it."""
    (tmp_path / "Jakefile.js").write_text("// jake")
    from luna_mcp.luna_config.jake_driver import JakeDriver
    driver = JakeDriver(project_path=str(tmp_path))
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Build OK"
    mock_result.stderr = ""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = driver.build(dry_run=False, execute=True)
    mock_run.assert_called_once()
    assert result.get("executed") is True
    assert result.get("returncode") == 0


def test_jake_driver_execute_false_no_subprocess(tmp_path):
    """execute=False must never call subprocess even when dry_run=False."""
    (tmp_path / "Jakefile.js").write_text("// jake")
    from luna_mcp.luna_config.jake_driver import JakeDriver
    driver = JakeDriver(project_path=str(tmp_path))
    with patch("subprocess.run") as mock_run:
        driver.build(dry_run=False, execute=False)
    mock_run.assert_not_called()


def test_jake_build_tool_dry_run(tmp_path):
    """MCP tool jake_build returns dry-run output without subprocess."""
    (tmp_path / "Jakefile.js").write_text("// jake")
    import asyncio

    from luna_mcp.tools.luna_config_tools import jake_build
    result = asyncio.run(jake_build(project_path=str(tmp_path)))
    assert "jake" in result.lower() or "dry" in result.lower()
    assert "execute" not in result.lower() or "false" in result.lower() or "dry" in result.lower()


def test_jake_build_tool_execute_mocked(tmp_path):
    """MCP tool jake_build with execute=True calls subprocess."""
    (tmp_path / "Jakefile.js").write_text("// jake")
    from luna_mcp.tools.luna_config_tools import jake_build
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Build OK"
    mock_result.stderr = ""
    import asyncio
    with patch("subprocess.run", return_value=mock_result):
        result = asyncio.run(jake_build(project_path=str(tmp_path), execute=True))
    assert "0" in result or "ok" in result.lower() or "Build OK" in result


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

def test_register_luna_config_tools():
    from unittest.mock import MagicMock

    from luna_mcp.tools.luna_config_tools import register_luna_config_tools
    mcp = MagicMock()
    mcp.tool.return_value = lambda fn: fn
    tools = register_luna_config_tools(mcp, exposed=set())
    assert "luna_config_get" in tools
    assert "luna_config_diff" in tools
    assert "luna_config_set" in tools
    assert "jake_build" in tools


def test_exposed_only_get_and_diff():
    """Only luna_config_get and luna_config_diff should be exposed."""
    from unittest.mock import MagicMock

    from luna_mcp.tools.luna_config_tools import register_luna_config_tools
    mcp = MagicMock()
    mcp.tool.return_value = lambda fn: fn
    exposed = {"luna_config_get", "luna_config_diff"}
    register_luna_config_tools(mcp, exposed=exposed)
    # tool() called exactly twice (once per exposed tool)
    assert mcp.tool.call_count == 2
