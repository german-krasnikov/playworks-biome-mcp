"""TDD tests for regression/differ.py — pixel diff + mask zones."""
import io
import pathlib

from PIL import Image

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "regression"


def _png_bytes(path: str) -> bytes:
    return (FIXTURES / path).read_bytes()


def _make_png(width: int, height: int, color=(128, 128, 128)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


# 1
def test_identical_returns_zero():
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "identical_a.png"
    current = _png_bytes("identical_b.png")
    pct, err = diff_pct(baseline, current)
    assert err is None
    assert pct == 0.0


# 2
def test_size_mismatch_error():
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "identical_a.png"  # 50x50
    current = _png_bytes("small_a.png")  # 30x30
    pct, err = diff_pct(baseline, current)
    assert err is not None
    assert "mismatch" in err


# 3
def test_full_diff_returns_high_pct():
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "color_diff_a.png"  # blue
    current = _png_bytes("color_diff_b.png")  # red
    pct, err = diff_pct(baseline, current)
    assert err is None
    assert pct > 50.0  # entirely different


# 4
def test_mask_zone_excludes_diff():
    """Diff region is masked → pct ~0."""
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "mask_a.png"   # white + red top-left 10x10
    current = _png_bytes("mask_b.png")   # white + green top-left 10x10
    # Without mask → should have diff
    pct_no_mask, _ = diff_pct(baseline, current)
    assert pct_no_mask > 0
    # With mask covering the diff region → pct should drop to ~0
    pct_masked, err = diff_pct(baseline, current, mask_zones="0,0,10,10")
    assert err is None
    assert pct_masked == 0.0


# 5
def test_parse_mask_zones_multi():
    from luna_mcp.regression.differ import parse_mask_zones
    zones = parse_mask_zones("0,0,10,10; 50,50,20,20; 100,100,5,5")
    assert zones == [(0, 0, 10, 10), (50, 50, 20, 20), (100, 100, 5, 5)]


# 6
def test_parse_mask_zones_invalid_skipped():
    from luna_mcp.regression.differ import parse_mask_zones
    zones = parse_mask_zones("0,0,10,10; not_valid; 20,20,5,5")
    assert zones == [(0, 0, 10, 10), (20, 20, 5, 5)]


# 7
def test_noise_threshold_filters_subtle():
    """Pixel diff of 2 (< default noise_threshold=3) is ignored."""
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "subtle_a.png"
    current = _png_bytes("subtle_b.png")
    pct, err = diff_pct(baseline, current, noise_threshold=3)
    assert err is None
    assert pct == 0.0


def test_parse_mask_zones_empty():
    from luna_mcp.regression.differ import parse_mask_zones
    assert parse_mask_zones("") == []


def test_diff_pct_with_mask_on_identical():
    from luna_mcp.regression.differ import diff_pct
    baseline = FIXTURES / "identical_a.png"
    current = _png_bytes("identical_b.png")
    pct, err = diff_pct(baseline, current, mask_zones="0,0,10,10")
    assert err is None
    assert pct == 0.0


def test_full_diff_no_mask_smoke():
    """Smoke: diff from in-memory PNGs."""
    from luna_mcp.regression.differ import diff_pct
    buf_a = io.BytesIO()
    buf_b = io.BytesIO()
    Image.new("RGB", (20, 20), color=(0, 0, 255)).save(buf_a, format="PNG")
    Image.new("RGB", (20, 20), color=(255, 0, 0)).save(buf_b, format="PNG")
    import pathlib as pl
    import tempfile
    tmp = pl.Path(tempfile.mktemp(suffix=".png"))
    tmp.write_bytes(buf_a.getvalue())
    try:
        pct, err = diff_pct(tmp, buf_b.getvalue())
        assert err is None
        assert pct > 50.0
    finally:
        tmp.unlink(missing_ok=True)
