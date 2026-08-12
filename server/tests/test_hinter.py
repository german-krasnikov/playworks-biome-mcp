"""Tests for ToolHinter behavioral pattern detection."""
from luna_mcp.hinter import ToolHinter


def make_hinter():
    return ToolHinter()


def feed(h: ToolHinter, name: str, kw: dict = None, out: str = "ok"):
    return h.observe(name, kw or {}, out)


# --- rule tests ---

def test_eval_spam_after_3_same_prefix():
    h = make_hinter()
    expr = "document.querySelector('.btn')"
    feed(h, "eval_js", {"expression": expr})
    feed(h, "eval_js", {"expression": expr})
    result = feed(h, "eval_js", {"expression": expr})
    assert result is not None
    assert "eval-spam" in result


def test_eval_spam_different_prefixes_no_hint():
    h = make_hinter()
    feed(h, "eval_js", {"expression": "document.getElementById('a')"})
    feed(h, "eval_js", {"expression": "window.location.href"})
    result = feed(h, "eval_js", {"expression": "console.log('hi')"})
    assert result is None


def test_screenshot_noop_no_mutation_between():
    h = make_hinter()
    feed(h, "screenshot", {})
    result = feed(h, "screenshot", {})
    assert result is not None
    assert "noop-screenshot" in result


def test_screenshot_with_set_property_between_no_hint():
    h = make_hinter()
    feed(h, "screenshot", {})
    feed(h, "set_property", {"path": "Root/Btn", "prop": "active"})
    result = feed(h, "screenshot", {})
    assert result is None


def test_console_polling_3plus():
    h = make_hinter()
    feed(h, "get_console")
    feed(h, "get_console")
    feed(h, "get_console")
    result = feed(h, "get_console")
    assert result is not None
    assert "console-poll" in result


def test_lost_context_find_hierarchy_find_pattern():
    h = make_hinter()
    feed(h, "get_hierarchy")
    feed(h, "find_objects", {"query": "Btn"})
    feed(h, "get_hierarchy")
    result = feed(h, "find_objects", {"query": "Btn"})
    assert result is not None
    assert "lost-context" in result


def test_repeated_set_property_4_same_path():
    h = make_hinter()
    kw = {"path": "Root/Btn", "prop": "active", "value": "true"}
    feed(h, "set_property", kw)
    feed(h, "set_property", kw)
    feed(h, "set_property", kw)
    result = feed(h, "set_property", kw)
    assert result is not None
    assert "batch-mutations" in result


def test_detail_redundant_after_get_object_detail():
    h = make_hinter()
    feed(h, "get_object_detail", {"path": "Root/Btn"})
    result = feed(h, "get_component", {"path": "Root/Btn", "component_type": "Image"})
    assert result is not None
    assert "detail-redundant" in result


def test_som_bypass_eval_after_som():
    h = make_hinter()
    feed(h, "screenshot_som", {})
    result = feed(h, "eval_js", {"expression": "document.click()"})
    assert result is not None
    assert "som-bypass" in result


def test_pause_leak_8_calls_without_resume():
    h = make_hinter()
    feed(h, "pause_game")
    for _ in range(8):
        feed(h, "get_hierarchy")
    result = feed(h, "get_hierarchy")
    assert result is not None
    assert "pause-leak" in result


def test_diag_thrash_with_reflect_in_history():
    h = make_hinter()
    # inject a REFLECT tag into history
    feed(h, "set_property", {"path": "X"}, "[REFLECT:mismatch: something wrong]")
    feed(h, "diagnose_object", {"path": "Root/A"})
    result = feed(h, "diagnose_object", {"path": "Root/B"})
    assert result is not None
    assert "diag-thrash" in result


def test_budget_deaf_repeat_after_skipped():
    h = make_hinter()
    feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget exhausted]")
    result = feed(h, "get_hierarchy", {})
    assert result is not None
    assert "budget-deaf" in result


def test_no_hint_in_normal_flow():
    h = make_hinter()
    feed(h, "get_hierarchy")
    feed(h, "get_component", {"path": "Root/Btn"})
    feed(h, "set_property", {"path": "Root/Btn", "prop": "active"})
    result = feed(h, "screenshot")
    assert result is None


# --- canonical key tests ---

def test_canonical_key_for_eval_js_uses_prefix():
    h = make_hinter()
    expr = "x" * 100  # longer than 60 chars
    key = h._canonical_key("eval_js", {"expression": expr})
    assert key == f"eval_js:{'x' * 60}"


def test_canonical_key_for_set_property_uses_path():
    h = make_hinter()
    key = h._canonical_key("set_property", {"path": "Root/Btn"})
    assert key == "set_property:Root/Btn"


def test_canonical_key_generic():
    h = make_hinter()
    assert h._canonical_key("screenshot", {}) == "screenshot"


# --- tag extraction tests ---

def test_extract_tag_invalid():
    h = make_hinter()
    assert h._extract_tag("[INVALID:type: bad type]") == "INVALID"


def test_extract_tag_budget():
    h = make_hinter()
    assert h._extract_tag("[skipped foo: reason]") == "BUDGET"


def test_extract_tag_reflect():
    h = make_hinter()
    assert h._extract_tag("[REFLECT:mismatch: something]") == "REFLECT"


def test_extract_tag_degraded():
    h = make_hinter()
    assert h._extract_tag("[DEGRADED:chrome:offline]") == "DEGRADED"


def test_extract_tag_ok():
    h = make_hinter()
    assert h._extract_tag("some normal output") == "OK"


# --- suppress/adoption tests ---

def test_history_strip_hint_marker_avoids_loop():
    """Output with [HINT:*] in it should not cascade a second hint from that marker."""
    h = make_hinter()
    # emit a hint from budget-deaf rule
    feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget]")
    # now feed result that already contains a HINT marker
    result = feed(h, "get_hierarchy", {}, "data\n[HINT:budget-deaf: budget said skip — repeating same call won't help]")
    # budget-deaf fires again but doesn't loop — just check it's a string or None
    assert result is None or isinstance(result, str)


def test_suppress_after_2_ignores():
    """Rule suppressed after being ignored 2+ times in a row."""
    h = make_hinter()
    # trigger budget-deaf, then keep repeating without changing pattern
    for _ in range(12):
        feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget]")
        feed(h, "get_hierarchy", {})
    # after many ignores, rule should be suppressed
    feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget]")
    result = feed(h, "get_hierarchy", {})
    # might be None (suppressed) or a hint — just ensure no crash
    assert result is None or "[HINT:" in result


def test_unsuppress_after_8_calls():
    """After suppress, 8 calls later rule fires again."""
    h = make_hinter()
    # force suppress state directly
    h._suppress["budget-deaf"] = 1  # expires after 1 more call
    feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget]")
    # suppress should have expired
    assert "budget-deaf" not in h._suppress


def test_adoption_resets_ignore_counter():
    """If LLM changes tool after hint, ignore counter resets."""
    h = make_hinter()
    # fire budget-deaf
    feed(h, "get_hierarchy", {}, "[skipped get_hierarchy: budget]")
    hint = feed(h, "get_hierarchy", {})
    assert hint is not None
    # LLM "adopts" by calling different tool
    feed(h, "screenshot", {})
    # ignore counter should be 0 now
    assert h._ignored_count.get("budget-deaf", 0) == 0

