"""Tests for F11 Smart Error Triage — TDD RED phase."""
import pytest

from luna_mcp.error_triage.triage import triage, triage_with_llm

# --- Tier 1: triage() ---

def test_dedup_counts():
    lines = ["[E 1] NullReferenceException in Foo"] * 35 + [
        f"[E {i}] SomeOtherError line {i}" for i in range(15)
    ]
    raw = "\n".join(lines)
    result = triage(raw)
    assert result["stats"]["dupes"] == 34  # 35 identical → 1 unique + 34 dupes
    assert len(result["groups"]) == 16  # 1 from NullRef + 15 unique


def test_severity_classification():
    raw = "[E 1] NullReferenceException\n[W 2] DOTween warning\n[I 3] info message"
    result = triage(raw)
    by_sev = {g["severity"]: g for g in result["groups"]}
    assert by_sev["critical"]["sample"] == "[E 1] NullReferenceException"
    assert by_sev["noise"]["sample"] == "[W 2] DOTween warning"
    assert by_sev["info"]["sample"] == "[I 3] info message"


def test_empty_console():
    result = triage("")
    assert result["stats"]["critical"] == 0
    assert result["stats"]["dupes"] == 0
    assert result["groups"] == []


def test_stats_fields():
    raw = "[E] NullReferenceException\n[E] SomeException\n[W] Canvas warning\n[I] just info"
    result = triage(raw)
    assert result["stats"]["critical"] == 2
    assert result["stats"]["noise"] == 1
    assert result["stats"]["info"] == 1


def test_ordering_critical_first():
    raw = "[I] info only\n[W] DOTween noise\n[E] NullReferenceException"
    result = triage(raw)
    severities = [g["severity"] for g in result["groups"]]
    assert severities[0] == "critical"
    assert severities[-1] == "noise"


def test_whitespace_only_lines_ignored():
    raw = "   \n\n[E] NullReferenceException\n\n  "
    result = triage(raw)
    assert len(result["groups"]) == 1


# --- Tier 2: triage_with_llm() ---

@pytest.mark.asyncio
async def test_tier1_only_when_sampling_none():
    raw = "[E] NullReferenceException\n[W] DOTween warning"
    out = await triage_with_llm(raw, None)
    assert "1 critical" in out
    assert "1 noise" in out
    assert "NullReferenceException" in out


@pytest.mark.asyncio
async def test_empty_returns_no_errors_message():
    out = await triage_with_llm("", None)
    assert "No errors" in out


@pytest.mark.asyncio
async def test_tier2_called_when_sampling_available():
    raw = "[E] NullReferenceException\n[W] DOTween warning"

    class FakeSampling:
        async def plan(self, intent: str, system: str, ctx: str = "") -> str:
            return "LLM summary: fix the NullRef in Foo"

    out = await triage_with_llm(raw, FakeSampling())
    assert "LLM summary" in out


@pytest.mark.asyncio
async def test_tier2_plan_none_falls_back_to_tier1():
    raw = "[E] NullReferenceException"

    class FakeSampling:
        async def plan(self, intent: str, system: str, ctx: str = ""):
            return None

    out = await triage_with_llm(raw, FakeSampling())
    assert "NullReferenceException" in out


# --- triage_tools registration ---

def test_register_triage_tools_returns_dict():
    from luna_mcp.tools.triage_tools import register_triage_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    async def fake_console(count=100):
        return ""

    tools = register_triage_tools(FakeMCP(), get_console_fn=fake_console, get_sampling=lambda: None)
    assert "triage_console" in tools


@pytest.mark.asyncio
async def test_triage_console_tool_no_errors():
    from luna_mcp.tools.triage_tools import register_triage_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    async def fake_console(count=100):
        return ""

    tools = register_triage_tools(FakeMCP(), get_console_fn=fake_console, get_sampling=lambda: None)
    fn, _ = tools["triage_console"]
    result = await fn()
    assert "No errors" in result
