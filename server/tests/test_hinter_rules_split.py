"""TDD: hinter_rules.py extraction — rules 1-10 must live in hinter_rules module."""


def test_hinter_rules_module_importable():
    from luna_mcp.hinter_rules import _RULES_BASE
    assert len(_RULES_BASE) == 10


def test_hinter_rules_ids_match():
    from luna_mcp.hinter_rules import _RULES_BASE
    ids = [r[0] for r in _RULES_BASE]
    assert ids == [
        "eval-spam", "noop-screenshot", "console-poll", "lost-context",
        "batch-mutations", "detail-redundant", "som-bypass", "pause-leak",
        "diag-thrash", "budget-deaf",
    ]


def test_hinter_rules_all_callable():
    from luna_mcp.hinter_rules import _RULES_BASE
    for rid, fn in _RULES_BASE:
        assert callable(fn), f"{rid} not callable"


def test_hinter_has_10_rules_total():
    """ToolHinter fires all 10 base rules."""
    import luna_mcp.hinter as mod
    assert len(mod._RULES) == 10


def test_hinter_file_under_200_lines():
    import inspect

    import luna_mcp.hinter as mod
    src = inspect.getsource(mod)
    lines = src.splitlines()
    assert len(lines) <= 200, f"hinter.py is {len(lines)} lines (limit 200)"
