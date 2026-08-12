"""TDD: macro tools (do/ask/endcard/gameplay/monetization)."""
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_sampling(enabled=True, plan_result="find_objects query=CTA"):
    svc = MagicMock()
    svc.enabled = enabled
    svc.plan = AsyncMock(return_value=plan_result)
    return svc


def _make_tools(sampling=None, execute_fn=None, tool_reg=None):
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.macro_tools import register_macro_tools
    mcp = FastMCP("test")
    if sampling is None:
        sampling = _make_sampling()
    if tool_reg is None:
        tool_reg = {"find_objects": None, "get_object_detail": None, "ping": None}
    if execute_fn is None:
        execute_fn = AsyncMock(return_value="[DRY-RUN OK] all 1 steps validated")

    tools = register_macro_tools(
        mcp,
        get_sampling=lambda: sampling,
        get_tool_registry=lambda: tool_reg,
        exposed=set(),
        execute_batch_fn=execute_fn,
    )
    return tools, execute_fn


# ── do ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_do_disabled_returns_degraded(monkeypatch):
    monkeypatch.delenv("LUNA_VISUAL_LLM", raising=False)
    sampling = _make_sampling(enabled=False)
    tools, _ = _make_tools(sampling=sampling)
    result = await tools["do"][0](intent="find the CTA")
    assert "DEGRADED" in result


@pytest.mark.asyncio
async def test_do_empty_plan_returns_unavailable():
    sampling = _make_sampling(plan_result="")
    tools, _ = _make_tools(sampling=sampling)
    result = await tools["do"][0](intent="do something")
    assert "PLANNER_UNAVAILABLE" in result or "unavailable" in result.lower()


@pytest.mark.asyncio
async def test_do_invalid_plan_via_dry_run():
    """dry_run returning [BATCH ABORTED] should surface PLAN_INVALID."""
    sampling = _make_sampling(plan_result="find_objects query=Test")

    async def fake_execute(plan, dry_run=False, mode="continue"):
        if dry_run:
            return "[BATCH ABORTED at step 1]\nbad command"
        return "real result"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["do"][0](intent="do something")
    assert "PLAN_INVALID" in result or "ABORTED" in result


@pytest.mark.asyncio
async def test_do_executes_after_dry_run_passes():
    """When dry_run passes, real execution happens and result is returned."""
    sampling = _make_sampling(plan_result="find_objects query=CTA")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(("dry" if dry_run else "real", plan))
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "found: CTA button"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["do"][0](intent="find CTA")
    assert "found: CTA button" in result
    assert ("dry", "find_objects query=CTA") in call_log
    assert ("real", "find_objects query=CTA") in call_log


@pytest.mark.asyncio
async def test_do_result_includes_plan():
    sampling = _make_sampling(plan_result="find_objects query=CTA")

    async def fake_execute(plan, dry_run=False, mode="continue"):
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "ok result"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["do"][0](intent="find CTA")
    assert "PLAN:" in result
    assert "find_objects query=CTA" in result


# ── ask ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_rejects_mutation_in_plan():
    """ask must reject plan lines using non-read-only tools."""
    sampling = _make_sampling(plan_result="set_property path=Root prop=x value=1")
    tools, _ = _make_tools(sampling=sampling)
    result = await tools["ask"][0](question="what color is the button?")
    assert "REJECTED" in result or "mutation" in result.lower()


@pytest.mark.asyncio
async def test_ask_executes_when_pure_read_only():
    """ask allows plan with only read-only tools."""
    sampling = _make_sampling(plan_result="find_objects query=CTA")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(dry_run)
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "CTA found"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["ask"][0](question="what buttons are visible?")
    assert "CTA found" in result
    assert True in call_log   # dry_run was called
    assert False in call_log  # real execution was called


@pytest.mark.asyncio
async def test_ask_disabled_returns_degraded():
    sampling = _make_sampling(enabled=False)
    tools, _ = _make_tools(sampling=sampling)
    result = await tools["ask"][0](question="any question")
    assert "DEGRADED" in result


# ── endcard / gameplay / monetization ────────────────────────────────────────

@pytest.mark.asyncio
async def test_endcard_runs_through_kind():
    sampling = _make_sampling(plan_result="find_objects query=Install")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(dry_run)
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "install found"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["endcard"][0](intent="check install button")
    assert "install found" in result
    assert len(call_log) == 2  # dry + real


@pytest.mark.asyncio
async def test_gameplay_runs_through_kind():
    sampling = _make_sampling(plan_result="pause_game")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(dry_run)
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "game paused"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["gameplay"][0](intent="pause for inspection")
    assert "game paused" in result


@pytest.mark.asyncio
async def test_monetization_runs_through_kind():
    sampling = _make_sampling(plan_result="get_console filter=analytics")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(dry_run)
        if dry_run:
            return "[DRY-RUN OK] all 1 steps validated"
        return "analytics: event fired"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["monetization"][0](intent="check analytics")
    assert "analytics: event fired" in result


@pytest.mark.asyncio
async def test_macro_uses_execute_batch_not_raw_send():
    """Verify execute_batch_fn is called, not internal _send."""
    sampling = _make_sampling(plan_result="find_objects query=X")
    execute_mock = AsyncMock(side_effect=lambda plan, dry_run=False, mode="continue":
        "[DRY-RUN OK] all 1 steps validated" if dry_run else "result")

    tools, _ = _make_tools(sampling=sampling, execute_fn=execute_mock)
    await tools["do"][0](intent="find X")
    assert execute_mock.call_count == 2  # dry + real


@pytest.mark.asyncio
async def test_kind_disabled_returns_degraded():
    for kind in ("endcard", "gameplay", "monetization"):
        sampling = _make_sampling(enabled=False)
        tools, _ = _make_tools(sampling=sampling)
        fn = tools[kind][0]
        result = await fn(intent="test")
        assert "DEGRADED" in result


@pytest.mark.asyncio
async def test_invalid_plan_aborted_surfaces():
    """[INVALID:...] in dry_run also triggers PLAN_INVALID."""
    sampling = _make_sampling(plan_result="get_object_detail path=Root")

    async def fake_execute(plan, dry_run=False, mode="continue"):
        if dry_run:
            return "[INVALID: path not found]"
        return "real"

    tools, _ = _make_tools(sampling=sampling, execute_fn=fake_execute)
    result = await tools["do"][0](intent="inspect root")
    assert "PLAN_INVALID" in result or "INVALID" in result


# ── M5: READ_ONLY_TOOLS completeness ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_accepts_find_objects_by_component():
    """M5: find_objects_by_component must be in READ_ONLY_TOOLS so ask() doesn't reject it."""
    from luna_mcp.macro.whitelist import READ_ONLY_TOOLS
    assert "find_objects_by_component" in READ_ONLY_TOOLS
    sampling = _make_sampling(plan_result="find_objects_by_component component_type=Button")
    call_log = []

    async def fake_execute(plan, dry_run=False, mode="continue"):
        call_log.append(dry_run)
        return "[DRY-RUN OK] all 1 steps validated" if dry_run else "found buttons"

    tools, _ = _make_tools(
        sampling=sampling,
        execute_fn=fake_execute,
        tool_reg={"find_objects_by_component": None, "ping": None},
    )
    result = await tools["ask"][0](question="find button components")
    assert "REJECTED" not in result
    assert "found buttons" in result


@pytest.mark.asyncio
async def test_ask_accepts_get_layers():
    """M5: get_layers is read-only and must not be rejected."""
    from luna_mcp.macro.whitelist import READ_ONLY_TOOLS
    assert "get_layers" in READ_ONLY_TOOLS


@pytest.mark.asyncio
async def test_ask_accepts_get_game_state():
    from luna_mcp.macro.whitelist import READ_ONLY_TOOLS
    assert "get_game_state" in READ_ONLY_TOOLS


def test_read_only_tools_complete():
    """M5: all expected read-only tool names present in whitelist."""
    from luna_mcp.macro.whitelist import READ_ONLY_TOOLS
    expected = {
        "find_objects_by_component", "get_layers", "get_game_state",
        "get_materials", "get_components_list", "get_shader_report",
        "audit_materials", "raycast", "compare_objects",
        "get_audio_sources", "get_deep_property",
    }
    missing = expected - READ_ONLY_TOOLS
    assert not missing, f"Missing from READ_ONLY_TOOLS: {missing}"


# ── M2: build_id cache reset on reconnect ────────────────────────────────────

def test_reconnect_resets_build_id_cache(monkeypatch):
    """M2: _on_reconnect must call build_id.reset_cache() to clear stale hash."""
    import luna_mcp.build_id as _build_id
    # Set a fake cached value
    _build_id._cached = "stale_hash_abc"
    # Simulate what _on_reconnect does in server.py
    _build_id.reset_cache()
    assert _build_id._cached is None


def test_on_reconnect_calls_build_id_reset():
    """M2: server._on_reconnect must import and call build_id.reset_cache()."""
    import inspect

    import luna_mcp.server as srv
    # The _on_reconnect is defined inside lifespan — check source contains the call
    src = inspect.getsource(srv)
    assert "build_id.reset_cache()" in src or "_build_id.reset_cache()" in src


# ── Registration path (middleware bypass fix) ─────────────────────────────────

def test_macro_tools_use_maybe_expose_not_mcp_decorator():
    """Macro tools must use maybe_expose, not @mcp.tool() directly.

    When exposed set excludes a macro tool, FastMCP must NOT have it registered.
    With @mcp.tool() the tool always registers regardless of the exposed set.
    With maybe_expose it only registers when in exposed.
    """
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.macro_tools import register_macro_tools

    mcp_empty = FastMCP("test-empty")
    register_macro_tools(
        mcp_empty,
        get_sampling=lambda: None,
        get_tool_registry=lambda: {},
        exposed=set(),          # nothing exposed
        execute_batch_fn=AsyncMock(),
    )
    # If @mcp.tool() is used, tools land in mcp._tool_manager regardless of exposed.
    # With maybe_expose they should NOT be registered when not in exposed.
    registered = {t.name for t in mcp_empty._tool_manager.list_tools()}
    macro_names = {"do", "ask", "endcard", "gameplay", "monetization"}
    assert not registered & macro_names, (
        f"Macro tools registered despite not being in exposed set: {registered & macro_names}"
    )


def test_macro_tools_register_when_in_exposed():
    """Macro tools must register with FastMCP when their name is in the exposed set."""
    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.macro_tools import register_macro_tools

    mcp_full = FastMCP("test-full")
    exposed = {"do", "ask", "endcard", "gameplay", "monetization"}
    register_macro_tools(
        mcp_full,
        get_sampling=lambda: None,
        get_tool_registry=lambda: {},
        exposed=exposed,
        execute_batch_fn=AsyncMock(),
    )
    registered = {t.name for t in mcp_full._tool_manager.list_tools()}
    assert exposed == registered & exposed, (
        f"Missing from FastMCP: {exposed - registered}"
    )
