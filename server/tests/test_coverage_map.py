"""Unit tests for coverage_map pure functions."""
import pytest

from luna_mcp.coverage_map import _build_marker_index, _enclosing_marker, _is_dead_fn


def test_build_marker_index_finds_markers():
    src = "line1\n/*Game.Foo.Bar start*/\nline3\n/*Game.Baz start*/\nline5"
    markers = _build_marker_index(src)
    assert len(markers) == 2
    # markers are (line, name) sorted by line
    assert markers[0][1] == "Game.Foo.Bar"
    assert markers[1][1] == "Game.Baz"


def test_enclosing_marker_picks_largest_le():
    markers = [(1, "A"), (10, "B"), (20, "C")]
    assert _enclosing_marker(markers, 15) == "B"
    assert _enclosing_marker(markers, 1) == "A"
    assert _enclosing_marker(markers, 20) == "C"
    assert _enclosing_marker(markers, 0) is None


def test_is_dead_fn_all_zero():
    fn = {"ranges": [{"startOffset": 0, "endOffset": 100, "count": 0}]}
    assert _is_dead_fn(fn) is True


def test_is_dead_fn_some_nonzero():
    fn = {"ranges": [
        {"startOffset": 0, "endOffset": 50, "count": 0},
        {"startOffset": 50, "endOffset": 100, "count": 1},
    ]}
    assert _is_dead_fn(fn) is False


def test_is_dead_fn_empty_ranges():
    fn = {"ranges": []}
    assert _is_dead_fn(fn) is False


@pytest.mark.asyncio
async def test_map_dead_functions_finds_method():
    """Coverage entry with dead fn at marker offset → returns C# method name."""
    from luna_mcp.coverage_map import map_dead_functions

    # Source: marker at line 2 (after \n at offset 6)
    source = "line1\n/*Game.Foo.Bar start*/\nline3\n"
    # offset_to_line("\n", 6) = 2 (after first \n)
    # Function starts at offset 6 (line 2 = marker line)

    class FakeMapper:
        def find_script_id(self, name):
            return "s1"

        async def get_source(self, sid):
            return source

    def require_mapper():
        return FakeMapper()

    coverage_result = [{
        "scriptId": "s1",
        "url": "UnityScriptsCompiler.js",
        "functions": [
            {
                "functionName": "deadFn",
                "ranges": [{"startOffset": 6, "endOffset": 200, "count": 0}],
            }
        ],
    }]
    result = await map_dead_functions(coverage_result, require_mapper, top=30)
    assert "Game.Foo.Bar" in result
    assert "DEAD" in result


@pytest.mark.asyncio
async def test_map_dead_functions_unmapped():
    """Dead fn with no enclosing marker → UNMAPPED."""
    from luna_mcp.coverage_map import map_dead_functions

    source = "no markers here\n"

    class FakeMapper:
        def find_script_id(self, name):
            return "s1"

        async def get_source(self, sid):
            return source

    coverage_result = [{
        "scriptId": "s1",
        "url": "UnityScriptsCompiler.js",
        "functions": [
            {"functionName": "fn", "ranges": [{"startOffset": 0, "endOffset": 100, "count": 0}]},
        ],
    }]
    result = await map_dead_functions(coverage_result, lambda: FakeMapper(), top=30)
    assert "UNMAPPED" in result


@pytest.mark.asyncio
async def test_map_dead_functions_no_unity_script():
    from luna_mcp.coverage_map import map_dead_functions

    class FakeMapper:
        def find_script_id(self, name):
            return None

        async def get_source(self, sid):
            return ""

    coverage_result = [{"scriptId": "s99", "url": "other.js", "functions": []}]
    result = await map_dead_functions(coverage_result, lambda: FakeMapper(), top=30)
    assert "[DEGRADED]" in result
