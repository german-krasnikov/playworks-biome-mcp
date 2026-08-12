"""Tests for AssetCatalog — RED phase."""
from __future__ import annotations

import pathlib

import pytest

from luna_mcp.asset_optimizer.catalog import Asset, AssetCatalog


def test_asset_dataclass():
    a = Asset(path="img.png", abs_path="/tmp/img.png", kind="texture", size=1024)
    assert a.kind == "texture"
    assert a.size == 1024


def test_catalog_invalid_dir(tmp_path):
    with pytest.raises(ValueError):
        AssetCatalog(tmp_path / "nonexistent")


def test_catalog_file_not_dir(tmp_path):
    f = tmp_path / "file.txt"
    f.write_bytes(b"x")
    with pytest.raises(ValueError):
        AssetCatalog(f)


def test_scan_classifies_texture(tmp_path):
    (tmp_path / "img.png").write_bytes(b"fake png")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert len(assets) == 1
    assert assets[0].kind == "texture"
    assert assets[0].path == "img.png"


def test_scan_classifies_kinds(tmp_path):
    (tmp_path / "img.png").write_bytes(b"fake")
    (tmp_path / "audio.mp3").write_bytes(b"fake")
    (tmp_path / "font.ttf").write_bytes(b"fake")
    (tmp_path / "model.glb").write_bytes(b"fake")
    (tmp_path / "data.json").write_bytes(b"fake")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    kinds = {a.kind for a in assets}
    assert "texture" in kinds
    assert "audio" in kinds
    assert "font" in kinds
    assert "mesh" in kinds
    assert "other" in kinds


def test_scan_skip_dotfiles(tmp_path):
    (tmp_path / ".hidden.png").write_bytes(b"should skip")
    (tmp_path / "visible.png").write_bytes(b"include")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert all(".hidden" not in a.path for a in assets)
    assert len(assets) == 1


def test_scan_skip_dotdirs(tmp_path):
    dotdir = tmp_path / ".git"
    dotdir.mkdir()
    (dotdir / "obj.png").write_bytes(b"fake")
    (tmp_path / "real.png").write_bytes(b"real")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert len(assets) == 1
    assert assets[0].path == "real.png"


def test_scan_max_files_cap(tmp_path):
    for i in range(20):
        (tmp_path / f"img{i}.png").write_bytes(b"x")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan(max_files=5)
    assert len(assets) == 5


def test_scan_sorted_by_size_desc(tmp_path):
    (tmp_path / "small.png").write_bytes(b"x")
    (tmp_path / "big.png").write_bytes(b"x" * 1000)
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert assets[0].size >= assets[-1].size


def test_total_size(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x" * 100)
    (tmp_path / "b.mp3").write_bytes(b"x" * 200)
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert cat.total_size(assets) == 300


def test_by_kind(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.png").write_bytes(b"x")
    (tmp_path / "c.mp3").write_bytes(b"x")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    by_kind = cat.by_kind(assets)
    assert len(by_kind["texture"]) == 2
    assert len(by_kind["audio"]) == 1


def test_scan_size_stored(tmp_path):
    data = b"x" * 500
    (tmp_path / "img.jpg").write_bytes(data)
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert assets[0].size == 500


def test_scan_abs_path(tmp_path):
    (tmp_path / "img.png").write_bytes(b"x")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert pathlib.Path(assets[0].abs_path).is_absolute()


def test_webp_is_texture(tmp_path):
    (tmp_path / "img.webp").write_bytes(b"x")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert assets[0].kind == "texture"


def test_jpeg_is_texture(tmp_path):
    (tmp_path / "img.jpeg").write_bytes(b"x")
    cat = AssetCatalog(tmp_path)
    assets = cat.scan()
    assert assets[0].kind == "texture"
