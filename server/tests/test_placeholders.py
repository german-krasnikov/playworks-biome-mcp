"""Tests for placeholder engine."""
import pytest

from luna_mcp.templates.placeholders import PlaceholderError, expand, parse_args


def test_simple_substitution():
    result = expand("hello {{name}}", {"name": "world"})
    assert result == "hello world"


def test_default_value():
    result = expand("count={{n|10}}", {})
    assert result == "count=10"


def test_default_value_overridden():
    result = expand("count={{n|10}}", {"n": "5"})
    assert result == "count=5"


def test_missing_arg_raises():
    with pytest.raises(PlaceholderError, match="missing required arg: path"):
        expand("get {{path}}", {})


def test_newline_in_value_raises():
    with pytest.raises(PlaceholderError, match="newline"):
        expand("val={{x}}", {"x": "line1\nline2"})


def test_multiple_placeholders():
    result = expand("{{a}} + {{b}} = {{c}}", {"a": "1", "b": "2", "c": "3"})
    assert result == "1 + 2 = 3"


def test_whitespace_in_placeholder():
    result = expand("{{ name }}", {"name": "ok"})
    assert result == "ok"


def test_default_whitespace_trimmed():
    result = expand("{{x| default_val }}", {})
    assert result == "default_val"


def test_parse_args_basic():
    result = parse_args("path=/Canvas/Btn count=5")
    assert result == {"path": "/Canvas/Btn", "count": "5"}


def test_parse_args_empty():
    assert parse_args("") == {}


def test_parse_args_quoted_value():
    result = parse_args('query="hello world"')
    assert result == {"query": "hello world"}


def test_parse_args_no_equals_skipped():
    result = parse_args("foo bar=baz")
    assert result == {"bar": "baz"}


def test_expand_no_placeholders():
    text = "get_hierarchy depth=2"
    assert expand(text, {}) == text


def test_template_value_with_spaces_quoted():
    """M3: values with spaces must be shell-quoted so shlex.split yields 2 tokens."""
    import shlex
    result = expand("find_objects query={{query}}", {"query": "Main Camera"})
    # the expanded line must survive shlex.split into exactly ["find_objects", "query=..."]
    parts = shlex.split(result)
    assert parts[0] == "find_objects"
    assert len(parts) == 2, f"expected 2 tokens, got {parts}"
    # the value extracted from token must equal original (unquoted)
    key, val = parts[1].split("=", 1)
    assert key == "query"
    assert val == "Main Camera"
