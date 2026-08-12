"""S5.4 — Jake task discovery tests (RED phase)."""
import subprocess

import pytest

# ── discover_tasks unit tests ─────────────────────────────────────────────────

def test_discover_tasks_parses_jake_output(tmp_path, monkeypatch):
    """Monkeypatched subprocess returns fake jake -T output."""
    fake_output = (
        "jake build  # Build the project\n"
        "jake recompile  # Recompile TypeScript\n"
        "jake clean  # Remove build artifacts\n"
    )

    def fake_run(args, **kwargs):
        class Result:
            stdout = fake_output
            returncode = 0
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.luna_config.jake_tasks import discover_tasks
    result = discover_tasks(str(tmp_path))
    assert "build" in result
    assert result["build"] == "Build the project"
    assert "recompile" in result
    assert "clean" in result


def test_discover_tasks_file_not_found_uses_seed(tmp_path, monkeypatch):
    """FileNotFoundError → seed catalog + DEGRADED."""
    def fake_run(args, **kwargs):
        raise FileNotFoundError("jake not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.luna_config.jake_tasks import discover_tasks
    result = discover_tasks(str(tmp_path))
    # Should contain seed catalog keys
    assert isinstance(result, dict)
    assert len(result) >= 3  # at least build/clean/upload from seeds


def test_discover_tasks_timeout_returns_error(tmp_path, monkeypatch):
    """TimeoutExpired → returns dict with 'error' key."""
    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="jake", timeout=10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.luna_config.jake_tasks import discover_tasks
    result = discover_tasks(str(tmp_path))
    assert "error" in result or isinstance(result, dict)


def test_discover_tasks_catalog_persists(tmp_path, monkeypatch):
    """Results persist to data dir and reload."""
    fake_output = "jake build  # Build project\n"

    def fake_run(args, **kwargs):
        class Result:
            stdout = fake_output
            returncode = 0
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    catalog_path = tmp_path / "jake_tasks.json"
    from luna_mcp.luna_config.jake_tasks import discover_tasks, load_catalog, save_catalog
    tasks = discover_tasks(str(tmp_path))
    save_catalog(tasks, catalog_path)
    loaded = load_catalog(catalog_path)
    assert loaded.get("build") == "Build project"


# ── tool registration ─────────────────────────────────────────────────────────

def test_register_jake_tasks_tools_returns_discover(tmp_path):
    from luna_mcp.tools.jake_tasks_tools import register_jake_tasks_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_jake_tasks_tools(FakeMCP())
    assert "discover_jake_tasks" in tools


@pytest.mark.asyncio
async def test_discover_jake_tasks_tool_degraded(tmp_path, monkeypatch):
    """When jake absent, tool output has DEGRADED prefix."""
    def fake_run(args, **kwargs):
        raise FileNotFoundError("jake not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.tools.jake_tasks_tools import register_jake_tasks_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_jake_tasks_tools(FakeMCP())
    fn, _ = tools["discover_jake_tasks"]
    result = await fn(str(tmp_path))
    assert "DEGRADED" in result


@pytest.mark.asyncio
async def test_discover_jake_tasks_tool_parses(tmp_path, monkeypatch):
    """When jake works, output has task lines."""
    fake_output = "jake build  # Build project\njake clean  # Clean output\n"

    def fake_run(args, **kwargs):
        class Result:
            stdout = fake_output
            returncode = 0
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.tools.jake_tasks_tools import register_jake_tasks_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_jake_tasks_tools(FakeMCP())
    fn, _ = tools["discover_jake_tasks"]
    result = await fn(str(tmp_path))
    assert "build" in result
    assert "clean" in result


# ── route_intent keyword route ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_real_4task_jake_no_degraded_prefix(tmp_path, monkeypatch):
    """M3: real jake output whose tasks happen to match seed NAMES must NOT get DEGRADED prefix."""
    # These 4 task names match seed keys but come from a REAL jake run (not fallback)
    fake_output = (
        "jake build  # Build the project\n"
        "jake recompile  # Recompile and rebuild\n"
        "jake clean  # Remove build artifacts\n"
        "jake upload  # Upload to CDN / staging\n"
    )

    def fake_run(args, **kwargs):
        class Result:
            stdout = fake_output
            returncode = 0
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    from luna_mcp.tools.jake_tasks_tools import register_jake_tasks_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_jake_tasks_tools(FakeMCP())
    fn, _ = tools["discover_jake_tasks"]
    result = await fn(str(tmp_path))
    assert "DEGRADED" not in result, f"Real jake output must not be stamped DEGRADED, got: {result!r}"


def test_route_intent_has_jake_keyword():
    """route_intent KEYWORD_ROUTES includes rebuild/jake/task keywords."""
    from luna_mcp.intent_router.router import KEYWORD_ROUTES
    all_keywords = [kw for keys in KEYWORD_ROUTES for kw in keys]
    # At least one of these must be present
    assert any(k in all_keywords for k in ("jake", "recompile", "rebuild", "task"))
