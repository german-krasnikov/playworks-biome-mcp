"""Tests for PatchOp DSL + validator — RED phase."""
from luna_mcp.build_intel.index import build_index
from luna_mcp.build_intel.patch_dsl import PatchOp, apply_op, validate

SAMPLE_TEXT = """\
// Line 1
// Line 2
// Line 3
// Line 4
// Line 5
// Line 6 version meta
var jpeg_config = {quality: 85};
var anchor_tag_here = true;
"""


def make_index(tmp_path, text=SAMPLE_TEXT):
    j = tmp_path / "Jakefile.js"
    j.write_text(text)
    return build_index(j)


def test_validate_ok(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(id="t1", intent="test", search="quality: 85", replace="quality: 65", expected_count=1)
    ok, reason = validate(op, SAMPLE_TEXT, idx)
    assert ok is True
    assert reason == ""


def test_validate_wrong_count(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(id="t2", intent="test", search="quality: 85", replace="quality: 65", expected_count=2)
    ok, reason = validate(op, SAMPLE_TEXT, idx)
    assert ok is False
    assert "1" in reason and "2" in reason


def test_validate_search_missing(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(id="t3", intent="test", search="NOTFOUND_XYZ", replace="x", expected_count=1)
    ok, reason = validate(op, SAMPLE_TEXT, idx)
    assert ok is False


def test_validate_version_sha_match(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(
        id="t4", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, expected_version_sha=idx.version_sha,
    )
    ok, _ = validate(op, SAMPLE_TEXT, idx)
    assert ok is True


def test_validate_version_sha_mismatch(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(
        id="t5", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, expected_version_sha="deadbeef00000000",
    )
    ok, reason = validate(op, SAMPLE_TEXT, idx)
    assert ok is False
    assert "version" in reason.lower() or "mismatch" in reason.lower()


def test_validate_anchor_before_ok(tmp_path):
    idx = make_index(tmp_path)
    # anchor_tag_here appears before quality (it doesn't — rearrange text)
    text = "jpeg_anchor_before = 1;\nvar cfg = {quality: 85};\n"
    j = tmp_path / "Jakefile.js"
    j.write_text(text)
    idx2 = build_index(j)
    op = PatchOp(
        id="t6", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, anchor_before="jpeg_anchor_before", max_distance=50,
    )
    ok, _ = validate(op, text, idx2)
    assert ok is True


def test_validate_anchor_before_too_far(tmp_path):
    idx = make_index(tmp_path)
    far_text = "jpeg_far = 1;\n" + "x\n" * 200 + "var cfg = {quality: 85};\n"
    j = tmp_path / "Jakefile.js"
    j.write_text(far_text)
    idx2 = build_index(j)
    op = PatchOp(
        id="t7", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, anchor_before="jpeg_far", max_distance=50,
    )
    ok, reason = validate(op, far_text, idx2)
    assert ok is False
    assert "anchor_before" in reason


def test_validate_anchor_after_ok(tmp_path):
    text = "var cfg = {quality: 85};\nafter_anchor_tag = true;\n"
    j = tmp_path / "Jakefile.js"
    j.write_text(text)
    idx = build_index(j)
    op = PatchOp(
        id="t8", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, anchor_after="after_anchor_tag", max_distance=50,
    )
    ok, _ = validate(op, text, idx)
    assert ok is True


def test_validate_anchor_after_missing(tmp_path):
    text = "var cfg = {quality: 85};\n"
    j = tmp_path / "Jakefile.js"
    j.write_text(text)
    idx = build_index(j)
    op = PatchOp(
        id="t9", intent="test", search="quality: 85", replace="quality: 65",
        expected_count=1, anchor_after="NOTFOUND_AFTER", max_distance=50,
    )
    ok, reason = validate(op, text, idx)
    assert ok is False
    assert "anchor_after" in reason


def test_apply_replaces(tmp_path):
    idx = make_index(tmp_path)
    op = PatchOp(id="ta", intent="t", search="quality: 85", replace="quality: 65", expected_count=1)
    result = apply_op(op, SAMPLE_TEXT)
    assert "quality: 65" in result
    assert "quality: 85" not in result


def test_apply_respects_count(tmp_path):
    text = "a=1; a=1; a=1;"
    j = tmp_path / "Jakefile.js"
    j.write_text(text)
    idx = build_index(j)
    op = PatchOp(id="tb", intent="t", search="a=1", replace="a=2", expected_count=1)
    result = apply_op(op, text)
    # replace only first occurrence (expected_count=1)
    assert result == "a=2; a=1; a=1;"
