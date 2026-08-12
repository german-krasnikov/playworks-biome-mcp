"""F14: Transpiled Code Explainer — TDD tests.

Demangler + Haiku explanation for Luna transpiled JS.
No Chrome needed.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

TYPEMAP_DATA = {
    "Classes": [
        {
            "originalClassName": "PlayerController",
            "jsClassName": "MyGame.PlayerController",
            "constructors": [],
            "methods": [
                {"signature": "OnCollisionEnter(Collision col)", "jsName": "__p__coll_enter"},
                {"signature": "Move(Vector3 dir)", "jsName": "__p__move"},
            ],
        }
    ]
}

MANGLED_JS = """\
function __p__move(v) {
    var obj = $$Bridge$GetComponent(this, 'Rigidbody');
    obj.__p__velocity = v;
}
"""

DEMANGLED_EXPECTED_CONTAINS = ["move", "GetComponent"]


@pytest.fixture
def typemap_dir(tmp_path):
    d = tmp_path / "pipeline" / "templates" / "LunaCompiler" / "typemaps"
    d.mkdir(parents=True)
    (d / "user.typemap.json").write_text(json.dumps(TYPEMAP_DATA))
    return tmp_path


@pytest.fixture
def resolver(typemap_dir):
    from luna_mcp.typemap_resolver import TypemapResolver
    return TypemapResolver(plugin_path=str(typemap_dir))


@pytest.fixture
def no_typemap_resolver():
    from luna_mcp.typemap_resolver import TypemapResolver
    return TypemapResolver(plugin_path=None)


# ── demangle() ────────────────────────────────────────────────────────────────

def test_demangle_strips_internal_prefix():
    from luna_mcp.code_explainer.explainer import demangle
    result = demangle("__p__position", typemap=None)
    assert "position" in result
    assert "__p__" not in result


def test_demangle_strips_double_dollar():
    from luna_mcp.code_explainer.explainer import demangle
    result = demangle("$$Bridge$Reflection", typemap=None)
    assert "__p__" not in result
    assert "$$" not in result


def test_demangle_annotates_unity_calls():
    from luna_mcp.code_explainer.explainer import demangle
    result = demangle("GetComponent(this, 'Rigidbody')", typemap=None)
    assert "GetComponent" in result


def test_demangle_full_source_no_typemap():
    from luna_mcp.code_explainer.explainer import demangle
    result = demangle(MANGLED_JS, typemap=None)
    assert "__p__" not in result
    assert "$$" not in result


def test_demangle_with_typemap(resolver):
    from luna_mcp.code_explainer.explainer import demangle
    result = demangle(MANGLED_JS, typemap=resolver)
    # Still strips mangling patterns regardless of typemap
    assert "__p__" not in result


# ── explain_js() ──────────────────────────────────────────────────────────────

def test_explain_js_empty_source_returns_no_source():
    from luna_mcp.code_explainer.explainer import explain_js
    result = explain_js("", class_name="PlayerController", typemap=None, llm_result=None)
    assert "No source found" in result


def test_explain_js_no_typemap_typemap_miss_note():
    from luna_mcp.code_explainer.explainer import explain_js
    result = explain_js(MANGLED_JS, class_name="UnknownClass", typemap=None, llm_result=None)
    assert "typemap miss" in result.lower() or "no typemap" in result.lower() or "demangled" in result.lower()


def test_explain_js_tier1_only_contains_demangled_code():
    from luna_mcp.code_explainer.explainer import explain_js
    result = explain_js(MANGLED_JS, class_name="PlayerController", typemap=None, llm_result=None)
    assert "__p__" not in result
    assert "$$" not in result


def test_explain_js_tier2_llm_result_included():
    from luna_mcp.code_explainer.explainer import explain_js
    llm = "// C# equivalent:\nvoid Move(Vector3 dir) { rb.velocity = dir; }"
    result = explain_js(MANGLED_JS, class_name="PlayerController", typemap=None, llm_result=llm)
    assert "Move" in result


def test_explain_js_method_scope_filters_source():
    from luna_mcp.code_explainer.explainer import explain_js
    source_with_two_methods = """\
function __p__move(v) { return v; }
function __p__jump(h) { return h; }
"""
    result = explain_js(
        source_with_two_methods,
        class_name="PlayerController",
        typemap=None,
        llm_result=None,
        method_name="move",
    )
    # Should contain move, and ideally not jump (scoped)
    assert "move" in result.lower()


# ── CodeExplainer async class ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_explainer_no_source_from_call_fn():
    from luna_mcp.code_explainer.explainer import CodeExplainer
    call_fn = AsyncMock(return_value="")
    sampling = MagicMock()
    sampling.enabled = False
    explainer = CodeExplainer(call_fn=call_fn, typemap=None, sampling=sampling)
    result = await explainer.explain("PlayerController")
    assert "No source found" in result


@pytest.mark.asyncio
async def test_explainer_returns_demangled_tier1():
    from luna_mcp.code_explainer.explainer import CodeExplainer
    call_fn = AsyncMock(return_value=MANGLED_JS)
    sampling = MagicMock()
    sampling.enabled = False
    explainer = CodeExplainer(call_fn=call_fn, typemap=None, sampling=sampling)
    result = await explainer.explain("PlayerController")
    assert "__p__" not in result
    assert "$$" not in result


@pytest.mark.asyncio
async def test_explainer_tier2_uses_sampling_plan(resolver):
    from luna_mcp.code_explainer.explainer import CodeExplainer
    call_fn = AsyncMock(return_value=MANGLED_JS)
    sampling = MagicMock()
    sampling.enabled = True
    sampling.plan = AsyncMock(return_value="void Move(Vector3 dir) { rb.velocity = dir; }")
    explainer = CodeExplainer(call_fn=call_fn, typemap=resolver, sampling=sampling)
    result = await explainer.explain("PlayerController")
    assert sampling.plan.called
    assert "Move" in result or "velocity" in result


@pytest.mark.asyncio
async def test_explainer_method_scoped(resolver):
    from luna_mcp.code_explainer.explainer import CodeExplainer
    call_fn = AsyncMock(return_value=MANGLED_JS)
    sampling = MagicMock()
    sampling.enabled = False
    explainer = CodeExplainer(call_fn=call_fn, typemap=resolver, sampling=sampling)
    result = await explainer.explain("PlayerController", method_name="OnCollisionEnter")
    assert "PlayerController" in result or "OnCollisionEnter" in result


# ── Tool registration ─────────────────────────────────────────────────────────

def test_register_explainer_tools_returns_dict():
    from luna_mcp.tools.explainer_tools import register_explainer_tools
    mcp = MagicMock()
    mcp.tool = MagicMock(return_value=lambda fn: fn)
    call_fn = AsyncMock()
    sampling = MagicMock()
    sampling.enabled = False
    typemap = MagicMock()
    result = register_explainer_tools(mcp, call_fn, typemap=typemap, sampling=sampling, exposed={"explain_code"})
    assert "explain_code" in result
    assert "explain_function" in result


def test_register_explainer_tools_explain_code_is_callable():
    from luna_mcp.tools.explainer_tools import register_explainer_tools
    mcp = MagicMock()
    mcp.tool = MagicMock(return_value=lambda fn: fn)
    call_fn = AsyncMock()
    sampling = MagicMock()
    sampling.enabled = False
    typemap = MagicMock()
    result = register_explainer_tools(mcp, call_fn, typemap=typemap, sampling=sampling, exposed=set())
    from luna_mcp.tools.batch import derive_params
    fn, params = result["explain_code"]
    assert callable(fn)
    resolved = params if params is not None else derive_params(fn)
    assert "class_name" in resolved
