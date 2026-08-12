"""Tests for TextureAnalyzer — RED phase."""
from __future__ import annotations

import pathlib

from PIL import Image

from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer, TextureInfo

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "textures"


def test_analyze_returns_texture_info():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "sprite.png"))
    assert isinstance(info, TextureInfo)


def test_analyze_dimensions():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "photo_large.png"))
    assert info.width == 512
    assert info.height == 512


def test_analyze_pixels():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "photo_large.png"))
    assert info.pixels == 512 * 512


def test_analyze_sprite_has_alpha():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "sprite.png"))
    assert info.has_alpha is True


def test_analyze_rgb_no_alpha(tmp_path):
    img = Image.new("RGB", (64, 64), (100, 100, 100))
    p = tmp_path / "rgb.png"
    img.save(p)
    a = TextureAnalyzer()
    info = a.analyze(str(p))
    assert info.has_alpha is False


def test_analyze_entropy_flat_is_low(tmp_path):
    img = Image.new("RGB", (64, 64), (200, 200, 200))
    p = tmp_path / "flat.png"
    img.save(p)
    a = TextureAnalyzer()
    info = a.analyze(str(p))
    assert info.entropy < 1.0


def test_analyze_entropy_noisy_is_high():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "photo_large.png"))
    assert info.entropy > 6.0


def test_classify_glyph_for_small_alpha():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "glyph_small.png"))
    assert info.classification == "glyph"


def test_classify_sprite_for_medium_alpha():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "sprite.png"))
    assert info.classification == "sprite"


def test_classify_photo_high_entropy_large():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "photo_large.png"))
    assert info.classification == "photo"


def test_classify_ui_small_no_alpha():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "ui_flat.png"))
    assert info.classification in ("ui", "glyph")  # 64x64 borderline


def test_corrupt_file_returns_default():
    a = TextureAnalyzer()
    info = a.analyze(str(FIXTURES / "corrupt.png"))
    assert info.classification == "unknown"
    assert info.width == 0
    assert info.height == 0


def test_nonexistent_file_returns_default():
    a = TextureAnalyzer()
    info = a.analyze("/tmp/does_not_exist_xyz.png")
    assert info.width == 0
    assert info.classification == "unknown"


def test_path_stored_in_info():
    a = TextureAnalyzer()
    path = str(FIXTURES / "sprite.png")
    info = a.analyze(path)
    assert info.path == path


# M3 — PIL absent fallback
def test_analyze_returns_default_when_pil_unavailable(monkeypatch, tmp_path):
    import luna_mcp.asset_optimizer.texture_analyzer as tx
    monkeypatch.setattr(tx, "_PIL_AVAILABLE", False)
    a = tx.TextureAnalyzer()
    info = a.analyze(str(tmp_path / "anything.png"))
    assert info.width == 0
    assert info.height == 0
    assert info.classification == "unknown"


# m4 — glyph boundary: exactly 64x64 RGBA should be "glyph"
def test_classify_glyph_at_exactly_64x64(tmp_path):
    from PIL import Image
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 128))
    p = tmp_path / "glyph64.png"
    img.save(p)
    a = TextureAnalyzer()
    info = a.analyze(str(p))
    assert info.classification == "glyph"
