from unittest.mock import patch

from luna_mcp.config import migrate_data_dir


def test_migrate_data_dir_happy_path(tmp_path):
    old = tmp_path / ".luna_mcp"
    new = tmp_path / ".playworks-biome-mcp"
    old.mkdir()
    (old / "lessons.db").write_text("data")

    with patch("luna_mcp.config.pathlib.Path.home", return_value=tmp_path), \
         patch("luna_mcp.config.data_dir", return_value=new):
        migrate_data_dir()

    assert not old.exists()
    assert (new / "lessons.db").read_text() == "data"


def test_migrate_data_dir_noop_if_new_exists(tmp_path):
    old = tmp_path / ".luna_mcp"
    new = tmp_path / ".playworks-biome-mcp"
    old.mkdir()
    new.mkdir()
    (old / "lessons.db").write_text("old_data")
    (new / "lessons.db").write_text("new_data")

    with patch("luna_mcp.config.pathlib.Path.home", return_value=tmp_path), \
         patch("luna_mcp.config.data_dir", return_value=new):
        migrate_data_dir()

    assert old.exists()  # old NOT deleted
    assert (new / "lessons.db").read_text() == "new_data"  # new NOT overwritten


def test_migrate_data_dir_noop_if_no_old(tmp_path):
    new = tmp_path / ".playworks-biome-mcp"

    with patch("luna_mcp.config.pathlib.Path.home", return_value=tmp_path), \
         patch("luna_mcp.config.data_dir", return_value=new):
        migrate_data_dir()

    assert not new.exists()  # nothing created


def test_migrate_data_dir_skips_symlink(tmp_path):
    real = tmp_path / "real_dir"
    real.mkdir()
    old = tmp_path / ".luna_mcp"
    old.symlink_to(real)
    new = tmp_path / ".playworks-biome-mcp"

    with patch("luna_mcp.config.pathlib.Path.home", return_value=tmp_path), \
         patch("luna_mcp.config.data_dir", return_value=new):
        migrate_data_dir()

    assert old.is_symlink()  # symlink preserved
    assert not new.exists()
