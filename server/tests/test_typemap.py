"""Phase 19: Typemap Integration -- TDD tests.

TypemapResolver parses Playworks typemap JSON files to resolve C# -> JS names.
No Chrome needed.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

# ── Fixtures ─────────────────────────────────────────────────────────────────

TYPEMAP_OBJECT = {
    "Classes": [
        {
            "originalClassName": "Object",
            "jsClassName": "UnityEngine.Object",
            "constructors": [
                {"signature": ".ctor()", "jsName": "ctor"},
            ],
            "methods": [
                {"signature": "Destroy(Object obj)", "jsName": "Destroy"},
                {"signature": "Destroy(Object obj, float t)", "jsName": "Destroy$1"},
                {"signature": "FindObjectOfType()", "jsName": "FindObjectOfType"},
            ],
        },
        {
            "originalClassName": "Transform",
            "jsClassName": "UnityEngine.Transform",
            "constructors": [],
            "methods": [
                {"signature": "MultiplyTo(Transform src, Transform destination)", "jsName": "MultiplyTo"},
            ],
        },
    ]
}

TYPEMAP_USER = {
    "Classes": [
        {
            "originalClassName": "GameManager",
            "jsClassName": "MyGame.GameManager",
            "constructors": [],
            "methods": [
                {"signature": "StartGame()", "jsName": "StartGame"},
            ],
        }
    ]
}


@pytest.fixture
def typemap_dir(tmp_path):
    """Create typemap directory structure with mock files."""
    d = tmp_path / "pipeline" / "templates" / "LunaCompiler" / "typemaps"
    d.mkdir(parents=True)
    (d / "unityengine.typemap.json").write_text(json.dumps(TYPEMAP_OBJECT))
    (d / "user.typemap.json").write_text(json.dumps(TYPEMAP_USER))
    return tmp_path  # plugin_path


@pytest.fixture
def resolver(typemap_dir):
    from luna_mcp.typemap_resolver import TypemapResolver
    return TypemapResolver(plugin_path=str(typemap_dir))


# ── TypemapResolver core ──────────────────────────────────────────────────────

def test_available_false_no_path():
    from luna_mcp.typemap_resolver import TypemapResolver
    r = TypemapResolver(plugin_path=None)
    # Ensure env var isn't set
    os.environ.pop("LUNA_PLUGIN_PATH", None)
    assert r.available is False


def test_available_false_bad_path():
    from luna_mcp.typemap_resolver import TypemapResolver
    r = TypemapResolver(plugin_path="/nonexistent/path")
    assert r.available is False


def test_available_true(typemap_dir):
    from luna_mcp.typemap_resolver import TypemapResolver
    r = TypemapResolver(plugin_path=str(typemap_dir))
    assert r.available is True


def test_load_lazy(typemap_dir):
    """Creating resolver must not read files (lazy load)."""
    from luna_mcp.typemap_resolver import TypemapResolver
    r = TypemapResolver(plugin_path=str(typemap_dir))
    assert r._loaded is False


def test_resolve_method_by_name(resolver):
    result = resolver.resolve_method("Object", "Destroy")
    # No signature given -> first match
    assert result == "Destroy"


def test_resolve_method_overload(resolver):
    result = resolver.resolve_method("Object", "Destroy", "Destroy(Object obj, float t)")
    assert result == "Destroy$1"


def test_resolve_method_not_found_class(resolver):
    result = resolver.resolve_method("NonExistent", "SomeMethod")
    assert result is None


def test_resolve_method_not_found_method(resolver):
    result = resolver.resolve_method("Object", "NonExistentMethod")
    assert result is None


def test_get_class_api_full(resolver):
    result = resolver.get_class_api("Object")
    assert "Object" in result
    assert "UnityEngine.Object" in result
    assert "Destroy" in result
    assert "METHODS" in result
    assert "CONSTRUCTORS" in result


def test_get_class_api_not_found(resolver):
    result = resolver.get_class_api("NoSuchClass")
    assert "not found" in result.lower()
    assert "NoSuchClass" in result


def test_find_class_by_js_name(resolver):
    from luna_mcp.typemap_resolver import TypemapResolver
    r = TypemapResolver(plugin_path=str(resolver._plugin_path))
    cls = r._find_class("UnityEngine.Object")
    assert cls is not None
    assert cls["originalClassName"] == "Object"


def test_find_class_by_dotted(resolver):
    """Dotted name 'UnityEngine.Transform' should fall back to short name."""
    cls = resolver._find_class("UnityEngine.Transform")
    assert cls is not None
    assert cls["originalClassName"] == "Transform"


def test_resolve_js_name(resolver):
    result = resolver.resolve_js_name("Object", "Destroy")
    assert result == "UnityEngine.Object.Destroy"


def test_cross_file_loading(resolver):
    """Classes from user.typemap.json must be discoverable."""
    result = resolver.resolve_method("GameManager", "StartGame")
    assert result == "StartGame"


def test_malformed_file_skipped(tmp_path):
    """Bad JSON in a typemap file should not crash the resolver."""
    from luna_mcp.typemap_resolver import TypemapResolver
    d = tmp_path / "pipeline" / "templates" / "LunaCompiler" / "typemaps"
    d.mkdir(parents=True)
    (d / "bad.typemap.json").write_text("NOT VALID JSON {{{")
    (d / "good.typemap.json").write_text(json.dumps(TYPEMAP_OBJECT))
    r = TypemapResolver(plugin_path=str(tmp_path))
    result = r.resolve_method("Object", "Destroy")
    assert result == "Destroy"


# ── Tools ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_mcp():
    m = MagicMock()
    m.tool.return_value = lambda fn: fn
    return m


@pytest.fixture
def typemap_tools(mock_mcp, resolver):
    from luna_mcp.tools.typemap_tools import register_typemap_tools
    tools = register_typemap_tools(mock_mcp, lambda: resolver)
    return tools


@pytest.mark.asyncio
async def test_resolve_method_tool(typemap_tools):
    fn, _ = typemap_tools["resolve_method"]
    result = await fn("Object", "Destroy")
    assert "Object.Destroy" in result
    assert "UnityEngine.Object.Destroy" in result


@pytest.mark.asyncio
async def test_get_class_api_tool(typemap_tools):
    fn, _ = typemap_tools["get_class_api"]
    result = await fn("Transform")
    assert "Transform" in result
    assert "MultiplyTo" in result


@pytest.mark.asyncio
async def test_tools_no_plugin(mock_mcp):
    from luna_mcp.tools.typemap_tools import register_typemap_tools
    from luna_mcp.typemap_resolver import TypemapResolver
    os.environ.pop("LUNA_PLUGIN_PATH", None)
    r = TypemapResolver(plugin_path=None)
    tools = register_typemap_tools(mock_mcp, lambda: r)
    fn, _ = tools["resolve_method"]
    result = await fn("Object", "Destroy")
    assert "error" in result.lower()


# ── Registration ──────────────────────────────────────────────────────────────

def test_typemap_tools_in_batch_registry():
    """Both tools must be registered in the batch tool registry."""
    import luna_mcp.server  # noqa: F401 — triggers registration
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    assert "resolve_method" in _TOOL_REGISTRY
    assert "get_class_api" in _TOOL_REGISTRY


def test_resolve_method_importable():
    """resolve_method must be importable from luna_mcp.server (globals export)."""
    from luna_mcp import server
    assert hasattr(server, "resolve_method")
    assert hasattr(server, "get_class_api")
