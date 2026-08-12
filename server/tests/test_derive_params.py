"""Tests for derive_params() — equivalence + coercion-parity (B5)."""
from __future__ import annotations

import pytest

from luna_mcp.tools.batch import _TOOL_REGISTRY, coerce_args, derive_params, register_batch_tool

# ── derive_params basics ──────────────────────────────────────────────────────

def test_derive_params_str_annotation():
    async def fn(path: str) -> str: ...
    assert derive_params(fn) == {"path": str}


def test_derive_params_int_annotation():
    async def fn(count: int = 10) -> str: ...
    assert derive_params(fn) == {"count": int}


def test_derive_params_float_annotation():
    async def fn(timeout: float = 30.0) -> str: ...
    assert derive_params(fn) == {"timeout": float}


def test_derive_params_bool_annotation():
    async def fn(active: bool = False) -> str: ...
    assert derive_params(fn) == {"active": bool}


def test_derive_params_no_params():
    async def fn() -> str: ...
    assert derive_params(fn) == {}


def test_derive_params_unknown_annotation_defaults_to_str():
    from typing import Optional
    async def fn(path: Optional[str] = None) -> str: ...
    # Optional[str] is not in {int,float,bool,str} so defaults to str
    assert derive_params(fn) == {"path": str}


def test_derive_params_unannotated_defaults_to_str():
    async def fn(query) -> str: ...
    assert derive_params(fn) == {"query": str}


def test_derive_params_skips_var_keyword():
    async def fn(path: str, **kw) -> str: ...
    assert derive_params(fn) == {"path": str}


def test_derive_params_skips_var_positional():
    async def fn(*args) -> str: ...
    assert derive_params(fn) == {}


def test_derive_params_multi_params():
    async def fn(expression: str, timeout: float = 30.0) -> str: ...
    assert derive_params(fn) == {"expression": str, "timeout": float}


# ── register_batch_tool sentinel (params=None) ────────────────────────────────

@pytest.fixture(autouse=True)
def clean_registry():
    original = dict(_TOOL_REGISTRY)
    yield
    _TOOL_REGISTRY.clear()
    _TOOL_REGISTRY.update(original)


def test_register_batch_tool_none_derives_params():
    """params=None sentinel causes derive_params to be called."""
    async def my_tool(path: str, count: int = 5) -> str: ...
    register_batch_tool("my_tool", my_tool, None)
    _, params = _TOOL_REGISTRY["my_tool"]
    assert params == {"path": str, "count": int}


def test_register_batch_tool_explicit_dict_unchanged():
    """explicit dict is not overridden."""
    async def fn(path: str) -> str: ...
    register_batch_tool("fn", fn, {"path": str, "extra": int})
    _, params = _TOOL_REGISTRY["fn"]
    assert params == {"path": str, "extra": int}


def test_register_batch_tool_none_no_params_gives_empty():
    """no-arg fn with None gives {}."""
    async def screenshot() -> str: ...
    register_batch_tool("screenshot", screenshot, None)
    _, params = _TOOL_REGISTRY["screenshot"]
    assert params == {}


# ── coercion parity with derived params ──────────────────────────────────────

def test_derived_params_coerce_int():
    async def fn(count: int = 50) -> str: ...
    p = derive_params(fn)
    assert coerce_args({"count": "5"}, p) == {"count": 5}


def test_derived_params_coerce_bool_true():
    async def fn(active: bool = False) -> str: ...
    p = derive_params(fn)
    assert coerce_args({"active": "true"}, p) == {"active": True}


def test_derived_params_coerce_bool_false():
    async def fn(active: bool = True) -> str: ...
    p = derive_params(fn)
    assert coerce_args({"active": "false"}, p) == {"active": False}


def test_derived_params_coerce_float():
    async def fn(timeout: float = 30.0) -> str: ...
    p = derive_params(fn)
    assert coerce_args({"timeout": "1.5"}, p) == {"timeout": 1.5}


# ── equivalence: diagnostics_tools representative sample ─────────────────────

def test_equivalence_eval_js():
    async def eval_js(expression: str, timeout: float = 30.0) -> str: ...
    declared = {"expression": str, "timeout": float}
    assert derive_params(eval_js) == declared


def test_equivalence_get_console():
    async def get_console(count: int = 50, level: str = "", since: int = -1) -> str: ...
    declared = {"count": int, "level": str, "since": int}
    assert derive_params(get_console) == declared


def test_equivalence_triage_console():
    async def triage_console(count: int = 100) -> str: ...
    declared = {"count": int}
    assert derive_params(triage_console) == declared


def test_equivalence_explain_code():
    async def explain_code(class_name: str) -> str: ...
    declared = {"class_name": str}
    assert derive_params(explain_code) == declared


def test_equivalence_explain_function():
    async def explain_function(class_name: str, method_name: str) -> str: ...
    declared = {"class_name": str, "method_name": str}
    assert derive_params(explain_function) == declared


def test_equivalence_click_marker():
    async def click_marker(marker_id: int) -> str: ...
    declared = {"marker_id": int}
    assert derive_params(click_marker) == declared
