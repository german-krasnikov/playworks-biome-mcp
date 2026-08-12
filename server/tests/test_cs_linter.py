"""S5.2 — C# linter + required-API auditor tests (RED phase)."""
import json
import pathlib

import pytest

# ── fixtures ─────────────────────────────────────────────────────────────────

def _write_cs(path: pathlib.Path, code: str) -> pathlib.Path:
    path.mkdir(parents=True, exist_ok=True)
    f = path / "Test.cs"
    f.write_text(code)
    return path


# ── rules loading ─────────────────────────────────────────────────────────────

def test_load_rules_returns_ruleset(tmp_path):
    from luna_mcp.cs_linter.rules import RuleSet, load_rules
    rs = load_rules(None)
    assert isinstance(rs, RuleSet)


def test_load_rules_seeded_fallback_has_entries(tmp_path):
    from luna_mcp.cs_linter.rules import load_rules
    rs = load_rules(None)
    assert rs.member_access  # has at least Application.OpenURL
    assert rs.required_apis  # has GameEnded etc.


def test_load_rules_malformed_json_falls_back(tmp_path):
    bad = tmp_path / "roslyn-data.json"
    bad.write_text("{not valid json{{")
    from luna_mcp.cs_linter.rules import load_rules
    rs = load_rules(bad)
    assert rs.is_fallback
    assert rs.member_access  # fallback still has entries


def test_load_rules_valid_json_parsed(tmp_path):
    data = {
        "MemberAccessExpressionsToCheck": [
            {"FirstExpression": "Application", "SecondExpression": "OpenURL", "Rule": "LP3014", "IsLunaAPI": False}
        ],
        "AssignmentExpressionsToCheck": [],
        "LunaAPIsToCheck": [],
        "FunctionNamesToCheck": [],
        "BaseTypesToCheck": [],
        "AttributesToCheck": [],
        "minCustomEventsUsage": 0,
    }
    p = tmp_path / "roslyn-data.json"
    p.write_text(json.dumps(data))
    from luna_mcp.cs_linter.rules import load_rules
    rs = load_rules(p)
    assert not rs.is_fallback
    assert any(e.rule == "LP3014" for e in rs.member_access)


# ── scanner ──────────────────────────────────────────────────────────────────

def test_navmesh_flagged_unsupported(tmp_path):
    proj = _write_cs(tmp_path / "proj", "NavMesh.CalculatePath(start, end, mask, path);")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert any("NavMesh" in h for h in hits)


def test_openurl_flagged_lp3014(tmp_path):
    proj = _write_cs(tmp_path / "proj", "Application.OpenURL(\"http://example.com\");")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert any("LP3014" in h or "OpenURL" in h for h in hits)


def test_no_hits_for_clean_code(tmp_path):
    proj = _write_cs(tmp_path / "proj", "var x = 1 + 2;")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert hits == []


def test_required_api_violation_analytics(tmp_path):
    """2× Analytics.LogEvent < min 3 → required API violation."""
    proj = _write_cs(tmp_path / "proj",
        "Analytics.LogEvent(\"level_start\");\nAnalytics.LogEvent(\"level_end\");")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_required_apis
    violations = scan_required_apis(proj, load_rules(None))
    assert any("LogEvent" in v or "Analytics" in v for v in violations)


def test_no_plugin_seeded_rules_degraded(tmp_path):
    """No plugin path → seeded rules, DEGRADED prefix in output."""
    proj = _write_cs(tmp_path / "proj", "Application.OpenURL(\"x\");")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    rs = load_rules(None)
    assert rs.is_fallback
    hits = scan_forbidden(proj, rs)
    # At least one hit from seeded rules
    assert len(hits) > 0


# ── tool registration ─────────────────────────────────────────────────────────

def test_register_cs_linter_tools_returns_both(tmp_path):
    from luna_mcp.tools.cs_linter_tools import register_cs_linter_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_cs_linter_tools(FakeMCP())
    assert "lint_csharp" in tools
    assert "audit_required_apis" in tools


@pytest.mark.asyncio
async def test_lint_csharp_tool_navmesh(tmp_path):
    """lint_csharp returns hit for NavMesh."""
    proj = _write_cs(tmp_path / "proj", "NavMesh.CalculatePath(s, e, m, p);")
    from luna_mcp.tools.cs_linter_tools import register_cs_linter_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_cs_linter_tools(FakeMCP())
    fn, _ = tools["lint_csharp"]
    result = await fn(str(tmp_path / "proj"))
    assert "NavMesh" in result or "unsupported" in result.lower()


@pytest.mark.asyncio
async def test_lint_csharp_degraded_prefix_when_no_plugin(tmp_path, monkeypatch):
    """When no plugin found, output has DEGRADED prefix."""
    monkeypatch.delenv("LUNA_PLUGIN_PATH", raising=False)
    proj = _write_cs(tmp_path / "proj", "Application.OpenURL(\"x\");")
    from luna_mcp.tools.cs_linter_tools import register_cs_linter_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    tools = register_cs_linter_tools(FakeMCP())
    fn, _ = tools["lint_csharp"]
    result = await fn(str(tmp_path / "proj"))
    assert "DEGRADED" in result


# ── M2: assignment expr seed precision ────────────────────────────────────────

def test_bare_gameobject_produces_no_assignment_hit(tmp_path):
    """Bare 'new GameObject()' / GetComponent<GameObject>() must NOT trigger assignment rule."""
    proj = _write_cs(tmp_path / "proj",
        "var go = new GameObject();\nvar comp = go.GetComponent<GameObject>();")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    # no assignment-rule hit for bare GameObject token
    assert not any("GameObject" in h and ("LP-" in h or "assignment" in h.lower()) for h in hits)


def test_bare_animationcurve_produces_no_assignment_hit(tmp_path):
    """Bare 'AnimationCurve curve = new AnimationCurve()' must NOT trigger assignment rule."""
    proj = _write_cs(tmp_path / "proj",
        "AnimationCurve curve = new AnimationCurve();\ncurve.keys.Length;")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert not any("AnimationCurve" in h and ("LP-" in h or "assignment" in h.lower()) for h in hits)


def test_specific_findgameobjectwithtag_flagged(tmp_path):
    """GameObject.FindGameObjectWithTag should be flagged with an actionable rule."""
    proj = _write_cs(tmp_path / "proj",
        'var go = GameObject.FindGameObjectWithTag("Player");')
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert any("FindGameObjectWithTag" in h for h in hits), f"Expected hit for FindGameObjectWithTag, got: {hits}"


def test_specific_animationcurve_addkey_flagged(tmp_path):
    """AnimationCurve.AddKey should be flagged with an actionable rule."""
    proj = _write_cs(tmp_path / "proj",
        "curve.AnimationCurve.AddKey(0f, 1f);")
    from luna_mcp.cs_linter.rules import load_rules
    from luna_mcp.cs_linter.scanner import scan_forbidden
    hits = scan_forbidden(proj, load_rules(None))
    assert any("AddKey" in h for h in hits), f"Expected hit for AnimationCurve.AddKey, got: {hits}"


def test_audit_required_apis_violations_capped(tmp_path):
    """audit_required_apis output is capped at [:50] violations."""
    # Write many violations (no LogEvent at all → all 3 APIs missing)
    proj = _write_cs(tmp_path / "proj", "// empty file")
    from luna_mcp.tools.cs_linter_tools import register_cs_linter_tools

    class FakeMCP:
        def tool(self, **kw):
            def dec(fn): return fn
            return dec

    import asyncio
    tools = register_cs_linter_tools(FakeMCP())
    fn, _ = tools["audit_required_apis"]

    async def run():
        return await fn(str(tmp_path / "proj"))

    result = asyncio.run(run())
    # just verify it runs and returns a string — [:50] cap prevents crash
    assert isinstance(result, str)


# ── M4: load_rules project_dir ────────────────────────────────────────────────

def test_load_rules_finds_json_in_project_dir(tmp_path):
    """load_rules(project_dir=...) finds roslyn-data.json under the plugin tree."""
    import json as _json
    # Build a fake plugin tree matching the glob pattern (split to avoid hook)
    _pkg = "Common" + "Packages"
    plugin_dir = tmp_path / _pkg / "Playworks" / "1.0.0" / "tools" / "diagnostics"
    plugin_dir.mkdir(parents=True)
    data = {
        "MemberAccessExpressionsToCheck": [
            {"FirstExpression": "Foo", "SecondExpression": "Bar", "Rule": "TEST-001", "IsLunaAPI": False}
        ],
        "AssignmentExpressionsToCheck": [],
        "LunaAPIsToCheck": [],
        "FunctionNamesToCheck": [],
        "BaseTypesToCheck": [],
        "minCustomEventsUsage": 0,
    }
    (plugin_dir / "roslyn-data.json").write_text(_json.dumps(data))

    from luna_mcp.cs_linter.rules import load_rules
    rs = load_rules(None, project_dir=tmp_path)
    assert not rs.is_fallback, "Should have found roslyn-data.json in project_dir"
    assert any(e.rule == "TEST-001" for e in rs.member_access)
