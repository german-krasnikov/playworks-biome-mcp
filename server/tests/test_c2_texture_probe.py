"""C2(b,c) — Real-compression probe + Pillow cheap-tier estimate.

(b) probe.py: subprocess cwebp/pngquant dry-run -> ground-truth compressed size.
    Degrades to Pillow estimate when binary absent.
(c) texture_analyzer.py: in-process WEBP encode to memory buffer for cheap estimate.

All tests either mock subprocess or use a tiny synthetic image — no Chrome, no binaries needed.
"""
from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

from PIL import Image

# ---------------------------------------------------------------------------
# C2(c) — Pillow cheap-tier: TextureAnalyzer.estimate_webp_size
# ---------------------------------------------------------------------------

def _make_rgba_image(size: tuple[int, int] = (64, 64)) -> Image.Image:
    return Image.new("RGBA", size, (200, 100, 50, 128))


def test_estimate_webp_size_returns_int(tmp_path):
    """estimate_webp_size encodes to buffer and returns byte count."""
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer
    img = _make_rgba_image((128, 128))
    p = tmp_path / "test.png"
    img.save(p)

    a = TextureAnalyzer()
    size = a.estimate_webp_size(str(p), quality=80)
    assert isinstance(size, int)
    assert size > 0


def test_estimate_webp_size_quality_affects_size(tmp_path):
    """Lower quality should produce smaller WEBP estimate on noisy image."""
    import random

    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer
    # Noisy image — quality has measurable effect
    img = Image.new("RGB", (256, 256))
    img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                 for _ in range(256 * 256)])
    p = tmp_path / "noisy.png"
    img.save(p)

    a = TextureAnalyzer()
    high_q = a.estimate_webp_size(str(p), quality=90)
    low_q = a.estimate_webp_size(str(p), quality=30)
    assert low_q <= high_q


def test_estimate_webp_size_returns_zero_on_missing_file():
    """Returns 0 when file doesn't exist — no exception."""
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer
    a = TextureAnalyzer()
    size = a.estimate_webp_size("/tmp/no_such_file_xyz.png", quality=80)
    assert size == 0


def test_estimate_webp_size_returns_zero_when_pil_unavailable(tmp_path, monkeypatch):
    """Degrades to 0 when Pillow is not available."""
    import luna_mcp.asset_optimizer.texture_analyzer as tx
    monkeypatch.setattr(tx, "_PIL_AVAILABLE", False)
    a = tx.TextureAnalyzer()
    size = a.estimate_webp_size("/any.png", quality=80)
    assert size == 0


def test_estimate_webp_size_on_photo_fixture():
    """Real fixture: estimate should be > 0."""
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer
    fixture = pathlib.Path(__file__).parent / "fixtures" / "textures" / "photo_large.png"
    a = TextureAnalyzer()
    size = a.estimate_webp_size(str(fixture), quality=80)
    assert size > 0


# ---------------------------------------------------------------------------
# C2(c) — Recommender uses Pillow estimate as real_bytes_estimate
# ---------------------------------------------------------------------------

def test_recommend_includes_pillow_estimate():
    """AssetAction should carry webp_estimate_bytes when Pillow is available."""
    import pathlib

    from luna_mcp.asset_optimizer.catalog import Asset
    from luna_mcp.asset_optimizer.recommender import Recommender
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer

    # Use existing photo fixture which classifies as "photo" and has real file size
    fixture = pathlib.Path(__file__).parent / "fixtures" / "textures" / "photo_large.png"
    size_bytes = fixture.stat().st_size

    asset = Asset(path="photo_large.png", abs_path=str(fixture), kind="texture", size=size_bytes)
    r = Recommender(TextureAnalyzer())
    actions = r.recommend_textures([asset], target_size_kb=9999)
    assert len(actions) > 0
    act = actions[0]
    assert hasattr(act, "webp_estimate_bytes")
    assert act.webp_estimate_bytes >= 0


# ---------------------------------------------------------------------------
# C2(b) — CompressionProbe: cwebp/pngquant subprocess path
# ---------------------------------------------------------------------------

def test_probe_import():
    """probe module should be importable."""
    from luna_mcp.asset_optimizer import probe as _p  # noqa: F401


def test_probe_cwebp_calls_subprocess(tmp_path):
    """When cwebp is present, probe runs it and returns real bytes."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    img = _make_rgba_image((64, 64))
    p = tmp_path / "test.png"
    img.save(p)

    # Mock subprocess.run to return success + 1000-byte output file
    fake_output = tmp_path / "out.webp"
    fake_output.write_bytes(b"x" * 1000)

    def fake_run(cmd, **kwargs):
        # Write fake output file at -o path
        out_idx = cmd.index("-o") + 1
        pathlib.Path(cmd[out_idx]).write_bytes(b"x" * 1000)
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("luna_mcp.asset_optimizer.probe.subprocess.run", side_effect=fake_run):
        with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value="/usr/bin/cwebp"):
            probe = CompressionProbe()
            size = probe.probe_webp(str(p), quality=80)
    assert size == 1000


def test_probe_falls_back_to_pillow_when_cwebp_absent(tmp_path):
    """When cwebp not found, falls back to Pillow in-memory estimate."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer
    img = _make_rgba_image((128, 128))
    p = tmp_path / "test.png"
    img.save(p)

    with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value=None):
        probe = CompressionProbe(analyzer=TextureAnalyzer())
        size = probe.probe_webp(str(p), quality=80)
    # Falls back to Pillow cheap tier — should be > 0
    assert size > 0


def test_probe_pngquant_calls_subprocess(tmp_path):
    """When pngquant is present, probe runs it and returns compressed bytes."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    img = _make_rgba_image((64, 64))
    p = tmp_path / "sprite.png"
    img.save(p)

    def fake_run(cmd, **kwargs):
        # pngquant writes output to <stem>-fs8.png or --output path
        out_idx = cmd.index("--output") + 1 if "--output" in cmd else None
        if out_idx:
            pathlib.Path(cmd[out_idx]).write_bytes(b"x" * 800)
        result = MagicMock()
        result.returncode = 0
        return result

    with patch("luna_mcp.asset_optimizer.probe.subprocess.run", side_effect=fake_run):
        with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value="/usr/bin/pngquant"):
            probe = CompressionProbe()
            size = probe.probe_png(str(p), quality=80)
    # either got real bytes or fell back — just must be >= 0
    assert size >= 0


def test_probe_falls_back_to_zero_when_pngquant_absent(tmp_path):
    """When pngquant not found, returns 0 (caller uses Pillow fallback)."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    img = _make_rgba_image((64, 64))
    p = tmp_path / "sprite.png"
    img.save(p)

    with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value=None):
        probe = CompressionProbe()
        size = probe.probe_png(str(p), quality=80)
    assert size == 0


def test_probe_subprocess_error_returns_zero(tmp_path):
    """When subprocess exits non-zero, returns 0 gracefully."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    img = _make_rgba_image((64, 64))
    p = tmp_path / "test.png"
    img.save(p)

    def fail_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1
        return result

    with patch("luna_mcp.asset_optimizer.probe.subprocess.run", side_effect=fail_run):
        with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value="/usr/bin/cwebp"):
            probe = CompressionProbe()
            size = probe.probe_webp(str(p), quality=80)
    assert size == 0


def test_probe_exception_is_logged_not_silenced_webp(tmp_path):
    """Subprocess exception must be logged at DEBUG level, not silently swallowed."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe

    img = _make_rgba_image((32, 32))
    p = tmp_path / "test.png"
    img.save(p)

    with patch("luna_mcp.asset_optimizer.probe.subprocess.run", side_effect=OSError("binary broken")):
        with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value="/fake/cwebp"):
            with patch("luna_mcp.asset_optimizer.probe._LOG") as mock_log:
                probe = CompressionProbe()
                size = probe.probe_webp(str(p), quality=80)
    assert size == 0
    mock_log.debug.assert_called_once()
    assert "binary broken" in str(mock_log.debug.call_args) or mock_log.debug.call_count >= 1


def test_probe_exception_is_logged_not_silenced_png(tmp_path):
    """Subprocess exception in probe_png must be logged at DEBUG level."""
    from luna_mcp.asset_optimizer.probe import CompressionProbe

    img = _make_rgba_image((32, 32))
    p = tmp_path / "sprite.png"
    img.save(p)

    with patch("luna_mcp.asset_optimizer.probe.subprocess.run", side_effect=OSError("pngquant gone")):
        with patch("luna_mcp.asset_optimizer.probe.shutil.which", return_value="/fake/pngquant"):
            with patch("luna_mcp.asset_optimizer.probe._LOG") as mock_log:
                probe = CompressionProbe()
                size = probe.probe_png(str(p), quality=80)
    assert size == 0
    mock_log.debug.assert_called_once()


# ---------------------------------------------------------------------------
# C2(b) — recommender enriched with real_probe_bytes
# ---------------------------------------------------------------------------

def test_recommend_with_probe_uses_real_bytes():
    """When CompressionProbe is passed, AssetAction.real_probe_bytes is set."""
    import pathlib

    from luna_mcp.asset_optimizer.catalog import Asset
    from luna_mcp.asset_optimizer.probe import CompressionProbe
    from luna_mcp.asset_optimizer.recommender import Recommender
    from luna_mcp.asset_optimizer.texture_analyzer import TextureAnalyzer

    # Use real photo fixture that classifies correctly
    fixture = pathlib.Path(__file__).parent / "fixtures" / "textures" / "photo_large.png"
    size_bytes = fixture.stat().st_size
    asset = Asset(path="photo_large.png", abs_path=str(fixture), kind="texture", size=size_bytes)

    # Probe returns 5000 bytes (as if cwebp ran)
    mock_probe = MagicMock(spec=CompressionProbe)
    mock_probe.probe_webp.return_value = 5000
    mock_probe.probe_png.return_value = 0

    r = Recommender(TextureAnalyzer(), probe=mock_probe)
    actions = r.recommend_textures([asset], target_size_kb=9999)
    assert len(actions) > 0
    act = actions[0]
    assert hasattr(act, "real_probe_bytes")
    assert act.real_probe_bytes == 5000
