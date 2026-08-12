"""Tests for Jakefile index builder — RED phase."""
from luna_mcp.build_intel.index import JakefileIndex, build_index

SAMPLE_JAKE = """\
// Line 1
// Line 2
// Line 3
// Line 4
// Line 5
// Line 6 version meta
task('default', function() {});
task("build", function() { doSomething(); });
task('compress', function() {
    var quality = 'quality: 85';
    var format = 'jpeg_compression_enabled';
});
var LONG_STRING = "this_is_an_anchor_string_for_patching";
var another = 'another_long_anchor_string_here';
"""


def make_jake(tmp_path, content=SAMPLE_JAKE):
    j = tmp_path / "Jakefile.js"
    j.write_text(content)
    return j


def test_returns_jakefile_index(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert isinstance(idx, JakefileIndex)


def test_path_is_absolute(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert idx.path == str(tmp_path / "Jakefile.js")


def test_extracts_task_names(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert "default" in idx.task_names
    assert "build" in idx.task_names
    assert "compress" in idx.task_names


def test_task_names_sorted_unique(tmp_path):
    content = "task('foo', f);\ntask('foo', g);\ntask('bar', h);"
    idx = build_index(make_jake(tmp_path, content))
    assert idx.task_names == sorted(set(idx.task_names))
    assert len(idx.task_names) == len(set(idx.task_names))


def test_anchors_unique(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert len(idx.anchors) == len(set(idx.anchors))


def test_anchors_min_length(tmp_path):
    idx = build_index(make_jake(tmp_path))
    for a in idx.anchors:
        assert len(a) >= 12, f"anchor too short: {a!r}"


def test_anchors_capped_at_200(tmp_path):
    # generate lots of strings
    lines = [f"var x{i} = 'anchor_string_{i:05d}_long_enough';" for i in range(300)]
    idx = build_index(make_jake(tmp_path, "\n".join(lines)))
    assert len(idx.anchors) <= 200


def test_version_sha_stable(tmp_path):
    j = make_jake(tmp_path)
    idx1 = build_index(j)
    idx2 = build_index(j)
    assert idx1.version_sha == idx2.version_sha


def test_version_sha_16_chars(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert len(idx.version_sha) == 16


def test_version_sha_changes_with_line6(tmp_path):
    j = make_jake(tmp_path, SAMPLE_JAKE)
    idx1 = build_index(j)
    # Change line 6
    modified = SAMPLE_JAKE.replace("// Line 6 version meta", "// Line 6 CHANGED")
    j.write_text(modified)
    idx2 = build_index(j)
    assert idx1.version_sha != idx2.version_sha


def test_line_count(tmp_path):
    idx = build_index(make_jake(tmp_path))
    assert idx.line_count == len(SAMPLE_JAKE.splitlines())


def test_size(tmp_path):
    j = make_jake(tmp_path)
    idx = build_index(j)
    assert idx.size == j.stat().st_size


def test_to_summary_contains_fields(tmp_path):
    idx = build_index(make_jake(tmp_path))
    s = idx.to_summary()
    assert "path=" in s
    assert "version_sha=" in s
    assert "tasks=" in s
    assert "anchors_count=" in s


def test_short_file_no_crash(tmp_path):
    j = tmp_path / "Jakefile.js"
    j.write_text("task('x', f);")
    idx = build_index(j)
    assert "x" in idx.task_names
    assert idx.version_sha != ""
