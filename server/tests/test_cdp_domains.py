"""Tests for cdp_domains pure utilities."""
from luna_mcp.cdp_domains import NETWORK_PRESETS, offset_to_line, truncate_lines


def test_offset_to_line_first_line():
    assert offset_to_line("abc\ndef", 0) == 1


def test_offset_to_line_second_line():
    src = "abc\ndef"
    assert offset_to_line(src, 4) == 2


def test_offset_to_line_at_newline():
    src = "abc\ndef"
    assert offset_to_line(src, 3) == 1  # the \n itself is on line 1


def test_offset_to_line_end():
    src = "a\nb\nc"
    assert offset_to_line(src, len(src) - 1) == 3


def test_truncate_no_truncate():
    assert truncate_lines([1, 2, 3], 5) == [1, 2, 3]


def test_truncate_adds_more_line():
    result = truncate_lines(list(range(10)), 3)
    assert len(result) == 4
    assert result[-1] == "... (+7 more)"


def test_truncate_exact_n():
    result = truncate_lines([1, 2, 3], 3)
    assert result == [1, 2, 3]


def test_presets_keys():
    assert set(NETWORK_PRESETS.keys()) == {"online", "offline", "slow", "3g", "4g"}


def test_presets_offline_shape():
    p = NETWORK_PRESETS["offline"]
    assert p["offline"] is True
    assert p["download"] == 0
    assert p["upload"] == 0


def test_presets_online_shape():
    p = NETWORK_PRESETS["online"]
    assert p["offline"] is False
    assert p["download"] == -1


def test_presets_3g_shape():
    p = NETWORK_PRESETS["3g"]
    assert p["latency"] == 400
    assert p["download"] == 400_000


def test_presets_4g_shape():
    p = NETWORK_PRESETS["4g"]
    assert p["latency"] == 70
    assert p["download"] == 4_000_000
