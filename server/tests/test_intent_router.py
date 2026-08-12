"""Tests for F13 Intent Router (smart dispatcher)."""
import pytest

from luna_mcp.intent_router.router import KEYWORD_ROUTES, route, route_tier1

# --- Tier 1 pure-Python keyword matching ---

def test_tier1_physics_keyword():
    plan = route_tier1("object is falling through floor", "")
    assert plan is not None
    assert "diagnose_physics" in plan


def test_tier1_performance_keyword():
    plan = route_tier1("game is laggy and fps drops", "")
    assert plan is not None
    assert "get_performance_metrics" in plan or "diagnose_rendering" in plan


def test_tier1_error_keyword():
    plan = route_tier1("null reference exception in console", "")
    assert plan is not None
    assert "get_console" in plan


def test_tier1_visible_keyword_with_path():
    plan = route_tier1("object is invisible", "Player/Mesh")
    assert plan is not None
    assert "Player/Mesh" in plan


def test_tier1_no_match_returns_none():
    result = route_tier1("something completely unrelated xyz123", "")
    assert result is None


def test_tier1_animation_keyword():
    plan = route_tier1("animator transition not working", "Cube")
    assert plan is not None
    assert "get_animator_state" in plan or "animation" in plan.lower()


def test_tier1_memory_keyword():
    plan = route_tier1("memory leak in heap", "")
    assert plan is not None
    assert "memory" in plan.lower() or "heap" in plan.lower() or "vram" in plan.lower()


def test_tier1_size_keyword():
    plan = route_tier1("build size too large", "/path/to/build")
    assert plan is not None
    assert "analyze_build" in plan


def test_tier1_path_substitution():
    plan = route_tier1("click button not working", "Canvas/Button")
    assert plan is not None
    assert "Canvas/Button" in plan


def test_tier1_case_insensitive():
    plan = route_tier1("PHYSICS broken", "")
    assert plan is not None
    assert "diagnose_physics" in plan


# --- Async route() function ---

@pytest.mark.asyncio
async def test_route_no_sampling_tier1_used():
    """When sampling is None, Tier 1 should be used."""
    calls = []

    async def fake_execute(plan, dry_run=False):
        calls.append(("execute", plan, dry_run))
        return "ok"

    result = await route("physics falling", "", None, [], fake_execute)
    assert "diagnose_physics" in calls[0][1]
    assert result == "ok"


@pytest.mark.asyncio
async def test_route_empty_intent_returns_error():
    async def fake_execute(plan, dry_run=False):
        return "ok"

    result = await route("", "", None, [], fake_execute)
    assert "[NO_ROUTE]" in result


@pytest.mark.asyncio
async def test_route_no_keyword_match_no_sampling_returns_no_route():
    async def fake_execute(plan, dry_run=False):
        return "ok"

    result = await route("totally irrelevant xyz999", "", None, [], fake_execute)
    assert "[NO_ROUTE]" in result


@pytest.mark.asyncio
async def test_route_sampling_disabled_falls_back_to_tier1():
    class FakeSampling:
        enabled = False

        async def plan(self, intent, system, ctx=""):
            return None

    async def fake_execute(plan, dry_run=False):
        return "result"

    result = await route("fps slow", "", FakeSampling(), ["get_performance_metrics"], fake_execute)
    assert result == "result"


@pytest.mark.asyncio
async def test_route_haiku_plan_valid_used():
    """When Haiku returns valid plan, use it instead of Tier 1."""
    class FakeSampling:
        enabled = True

        async def plan(self, intent, system, ctx=""):
            return "get_performance_metrics"

    dry_calls = []

    async def fake_execute(plan, dry_run=False):
        if dry_run:
            dry_calls.append(plan)
            return "[DRY-RUN OK] all 1 steps validated"
        return "haiku_result"

    result = await route("fps drop", "", FakeSampling(), ["get_performance_metrics"], fake_execute)
    assert result == "haiku_result"
    assert len(dry_calls) == 1


@pytest.mark.asyncio
async def test_route_haiku_plan_invalid_falls_back_to_tier1():
    """When Haiku plan fails dry_run, fall back to Tier 1."""
    class FakeSampling:
        enabled = True

        async def plan(self, intent, system, ctx=""):
            return "nonexistent_tool"

    execute_calls = []

    async def fake_execute(plan, dry_run=False):
        execute_calls.append((plan, dry_run))
        if dry_run:
            return "[BATCH ABORTED at step 1]\nUnknown command: nonexistent_tool"
        return "tier1_result"

    result = await route("physics collision", "", FakeSampling(), ["diagnose_physics"], fake_execute)
    # should have fallen back to tier1, then executed tier1 plan
    real_calls = [(p, dr) for p, dr in execute_calls if not dr]
    assert len(real_calls) == 1
    assert "diagnose_physics" in real_calls[0][0]
    assert result == "tier1_result"


# --- Tool registration ---

def test_register_intent_tools_returns_dict():
    from luna_mcp.tools.intent_tools import register_intent_tools

    class FakeMCP:
        def tool(self):
            def decorator(fn):
                return fn
            return decorator

    registered = register_intent_tools(FakeMCP(), set(), None, [], lambda p, dr=False: None)
    assert "route_intent" in registered


def test_keyword_routes_all_tuples():
    """All keys in KEYWORD_ROUTES must be tuples of strings."""
    for key, val in KEYWORD_ROUTES.items():
        assert isinstance(key, tuple), f"Key {key!r} must be a tuple"
        assert all(isinstance(k, str) for k in key)
        assert isinstance(val, str)
