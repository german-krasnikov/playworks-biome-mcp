"""TDD: macro/prompts.py"""


def test_head_includes_whitelist_placeholder():
    from luna_mcp.macro.prompts import HEAD
    assert "{whitelist}" in HEAD


def test_do_tail_present():
    from luna_mcp.macro.prompts import DO_TAIL
    assert "discover" in DO_TAIL.lower() or "inspect" in DO_TAIL.lower() or "find" in DO_TAIL.lower()


def test_ask_tail_forbids_mutations():
    from luna_mcp.macro.prompts import ASK_TAIL
    assert "NEVER" in ASK_TAIL or "READ-ONLY" in ASK_TAIL
    assert "set_property" in ASK_TAIL or "set_transform" in ASK_TAIL


def test_endcard_tail_mentions_install_action():
    from luna_mcp.macro.prompts import ENDCARD_TAIL
    assert "Install" in ENDCARD_TAIL or "install" in ENDCARD_TAIL
    assert "EndCard" in ENDCARD_TAIL or "endcard" in ENDCARD_TAIL.lower()


def test_gameplay_tail_mentions_rigidbody_or_animator():
    from luna_mcp.macro.prompts import GAMEPLAY_TAIL
    assert "Animator" in GAMEPLAY_TAIL or "Rigidbody" in GAMEPLAY_TAIL or "gameplay" in GAMEPLAY_TAIL.lower()


def test_monetization_tail_mentions_cta_or_mraid():
    from luna_mcp.macro.prompts import MONETIZATION_TAIL
    assert "CTA" in MONETIZATION_TAIL or "mraid" in MONETIZATION_TAIL or "MRAID" in MONETIZATION_TAIL


def test_kind_to_tail_unknown_falls_back_to_do():
    from luna_mcp.macro.prompts import DO_TAIL, KIND_TO_TAIL
    assert KIND_TO_TAIL.get("unknown_kind", DO_TAIL) is DO_TAIL


def test_kind_to_tail_has_all_five():
    from luna_mcp.macro.prompts import KIND_TO_TAIL
    for kind in ("do", "ask", "endcard", "gameplay", "monetization"):
        assert kind in KIND_TO_TAIL


def test_build_prompt_concatenates():
    from luna_mcp.macro.prompts import build_prompt
    result = build_prompt("do", "tool_a | tool_b")
    assert "tool_a | tool_b" in result
    assert len(result) > 50


def test_build_prompt_ask_includes_readonly_note():
    from luna_mcp.macro.prompts import build_prompt
    result = build_prompt("ask", "find_objects")
    assert "NEVER" in result or "READ-ONLY" in result


def test_build_prompt_unknown_kind_uses_do_tail():
    from luna_mcp.macro.prompts import DO_TAIL, build_prompt
    result = build_prompt("nonexistent_kind", "tools")
    # Should fall back to DO_TAIL content
    first_word = DO_TAIL.split()[0]
    assert first_word in result
