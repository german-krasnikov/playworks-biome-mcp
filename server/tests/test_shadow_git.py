"""Tests for ShadowGit atomic apply/revert — RED phase."""
from luna_mcp.build_intel.shadow_git import ShadowGit


def test_init_creates_repo(tmp_path):
    sg = ShadowGit(tmp_path, "test_proj")
    assert sg.init_if_needed() is True
    assert (tmp_path / "test_proj" / ".git").exists()


def test_init_idempotent(tmp_path):
    sg = ShadowGit(tmp_path, "test_proj")
    sg.init_if_needed()
    assert sg.init_if_needed() is True  # second call ok


def test_stage_copies_file(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    src = tmp_path / "sample.txt"
    src.write_text("hello")
    dest = sg.stage_file(src, "sample.txt")
    assert dest.exists()
    assert dest.read_text() == "hello"


def test_commit_returns_sha(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    src = tmp_path / "f.js"
    src.write_text("var x = 1;")
    sg.stage_file(src, "f.js")
    sha = sg.commit("test patch")
    assert sha is not None
    assert len(sha) >= 7


def test_commit_and_revert(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    src = tmp_path / "f.js"
    src.write_text("var x = 1;")
    sg.stage_file(src, "f.js")
    sha = sg.commit("patch v1")
    assert sha is not None
    # modify file
    src.write_text("var x = 2;")
    sg.stage_file(src, "f.js")
    sha2 = sg.commit("patch v2")
    assert sha2 is not None
    # revert to before sha2
    ok = sg.revert_commit(sha2)
    assert ok is True


def test_revert_bad_sha(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    ok = sg.revert_commit("deadbeefdeadbeef1234deadbeef1234deadbeef")
    assert ok is False


def test_get_file_returns_none_if_missing(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    assert sg.get_file("nonexistent.js") is None


def test_get_file_returns_path(tmp_path):
    sg = ShadowGit(tmp_path, "proj")
    sg.init_if_needed()
    src = tmp_path / "x.js"
    src.write_text("content")
    sg.stage_file(src, "x.js")
    p = sg.get_file("x.js")
    assert p is not None
    assert p.read_text() == "content"


def test_multiple_projects_isolated(tmp_path):
    sg1 = ShadowGit(tmp_path, "proj1")
    sg2 = ShadowGit(tmp_path, "proj2")
    sg1.init_if_needed()
    sg2.init_if_needed()
    assert (tmp_path / "proj1" / ".git").exists()
    assert (tmp_path / "proj2" / ".git").exists()
