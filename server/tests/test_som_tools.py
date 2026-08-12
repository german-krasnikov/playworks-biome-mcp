"""TDD tests for Set-of-Mark (SoM) feature — luna_mcp."""
import io
import time

import pytest
from PIL import Image

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_image(w=800, h=600) -> Image.Image:
    return Image.new("RGB", (w, h), (200, 200, 200))


def _png_bytes(w=800, h=600) -> bytes:
    buf = io.BytesIO()
    _make_image(w, h).save(buf, "PNG")
    return buf.getvalue()


def _rect(path, x, y, w, h, kind="Button"):
    return {"path": path, "x": x, "y": y, "w": w, "h": h, "kind": kind}


# ── extract.py tests ──────────────────────────────────────────────────────────

def test_extract_filter_top_k_by_area():
    from luna_mcp.som.extract import extract_rects
    rects = [{"path": f"/E{i}", "x": i*10, "y": 0, "w": i+1, "h": i+1, "kind":"Button"} for i in range(30)]
    result = extract_rects(rects, 800, 600, top_k=10)
    assert len(result) == 10
    areas = [r["w"]*r["h"] for r in result]
    assert areas == sorted(areas, reverse=True)


def test_extract_min_size_dropped():
    from luna_mcp.som.extract import extract_rects
    rects = [
        _rect("/Big", 0, 0, 100, 100),
        _rect("/Tiny", 10, 10, 11, 11),  # 11 < 12 → dropped
    ]
    paths = [r["path"] for r in extract_rects(rects, 800, 600)]
    assert "/Big" in paths
    assert "/Tiny" not in paths


def test_extract_offscreen_culled():
    from luna_mcp.som.extract import extract_rects
    rects = [
        _rect("/InView", 100, 100, 100, 100),
        _rect("/OffLeft", -200, 100, 50, 50),
        _rect("/OffTop", 100, -200, 50, 50),
        _rect("/OffRight", 900, 100, 50, 50),  # x(900) >= img_w(800) → culled
    ]
    paths = [r["path"] for r in extract_rects(rects, 800, 600)]
    assert "/InView" in paths
    assert "/OffLeft" not in paths
    assert "/OffTop" not in paths
    assert "/OffRight" not in paths


# ── overlay.py tests ──────────────────────────────────────────────────────────

def test_overlay_renders_marker_ids():
    from luna_mcp.som.overlay import annotate
    img = _make_image()
    rects = [
        _rect("/Canvas/Btn1", 50, 50, 100, 40),
        _rect("/Canvas/Btn2", 200, 50, 100, 40),
    ]
    result, legend = annotate(img.copy(), rects)
    assert isinstance(result, Image.Image)
    assert "1=" in legend
    assert "2=" in legend
    # image pixels changed (markers drawn)
    assert result.tobytes() != img.tobytes()


def test_overlay_collision_push():
    from luna_mcp.som.overlay import LABEL_R, _compute_centers, _resolve_collisions
    rects = [{"path": f"/E{i}", "x": 5, "y": 5+i*2, "w": 50, "h": 20} for i in range(5)]
    centers = _resolve_collisions(_compute_centers(rects))
    for i in range(len(centers)):
        for j in range(i+1, len(centers)):
            cx1,cy1 = centers[i]; cx2,cy2 = centers[j]
            dist = ((cx1-cx2)**2 + (cy1-cy2)**2)**0.5
            assert dist >= LABEL_R * 2, f"Centers {i},{j} too close: {dist:.1f}"


def test_overlay_empty_rects():
    from luna_mcp.som.overlay import annotate
    img = _make_image()
    original = img.tobytes()
    result, legend = annotate(img.copy(), [])
    assert legend == "(no marks)"
    assert result.tobytes() == original


# ── marker_map.py tests ───────────────────────────────────────────────────────

def test_marker_map_set_and_get():
    from luna_mcp.state.marker_map import MarkerMap, Rect
    mm = MarkerMap()
    mm.set([Rect(id=1, path="/Btn", x=10, y=20, w=100, h=40, kind="Button")])
    r = mm.get(1)
    assert r is not None
    assert r.path == "/Btn"
    assert r.kind == "Button"


def test_marker_map_get_missing_returns_none():
    from luna_mcp.state.marker_map import MarkerMap
    mm = MarkerMap()
    assert mm.get(99) is None


def test_marker_map_expired_after_ttl():
    from luna_mcp.state.marker_map import MarkerMap, Rect
    mm = MarkerMap(ttl=0.01)  # 10ms TTL for testing
    mm.set([Rect(1, "/Btn", 0, 0, 100, 40, "Button")])
    time.sleep(0.02)
    assert mm.expired()


def test_marker_map_not_expired_within_ttl():
    from luna_mcp.state.marker_map import MarkerMap, Rect
    mm = MarkerMap(ttl=300)
    mm.set([Rect(1, "/Btn", 0, 0, 100, 40, "Button")])
    assert not mm.expired()


def test_marker_map_clear():
    from luna_mcp.state.marker_map import MarkerMap, Rect
    mm = MarkerMap()
    mm.set([Rect(1, "/Btn", 0, 0, 100, 40, "Button")])
    mm.clear()
    assert mm.get(1) is None
    assert mm.expired()


# ── som_tools.py tests ────────────────────────────────────────────────────────

MOCK_RECTS_TEXT = (
    "/Canvas/EndCard/InstallBtn|50|400|200|80|Button\n"
    "/Canvas/Hero|100|100|300|200|Renderer\n"
    "/Canvas/CloseBtn|700|10|60|60|Button"
)


@pytest.mark.asyncio
async def test_screenshot_som_populates_map():
    """screenshot_som: JS text → parsed → MarkerMap populated."""
    from luna_mcp.tools.som_tools import _parse_rect_lines
    rects = _parse_rect_lines(MOCK_RECTS_TEXT)
    assert len(rects) == 3
    assert rects[0]["path"] == "/Canvas/EndCard/InstallBtn"
    assert rects[0]["x"] == 50
    assert rects[0]["kind"] == "Button"


@pytest.mark.asyncio
async def test_screenshot_som_returns_path_and_legend():
    """screenshot_som returns file path + numbered legend."""
    import os

    from luna_mcp.state.marker_map import MarkerMap
    from luna_mcp.tools.som_tools import _build_som_result

    marker_map = MarkerMap()
    rects = [
        {"path": "/Canvas/EndCard/InstallBtn", "x": 50, "y": 400, "w": 200, "h": 80, "kind": "Button"},
        {"path": "/Canvas/Hero", "x": 100, "y": 100, "w": 300, "h": 200, "kind": "Renderer"},
    ]
    png = _png_bytes()
    result = _build_som_result(png, rects, marker_map)
    lines = result.split("\n")
    assert lines[0].endswith(".png")
    assert os.path.exists(lines[0])
    assert any("Button" in l for l in lines[1:])
    # cleanup
    os.unlink(lines[0])


@pytest.mark.asyncio
async def test_click_marker_dispatches_at_center():
    """click_marker resolves id → (cx,cy) → simulate_click called."""
    from luna_mcp.state.marker_map import MarkerMap, Rect
    from luna_mcp.tools.som_tools import _make_click_marker

    marker_map = MarkerMap()
    marker_map.set([Rect(1, "/Canvas/Btn", 100, 200, 80, 40, "Button")])

    clicked = []
    async def fake_click(x, y):
        clicked.append((x, y))
        return f"clicked ({x}, {y})"

    click_marker = _make_click_marker(marker_map, fake_click)
    result = await click_marker(1)
    assert clicked == [(140, 220)]  # center: 100+80//2, 200+40//2
    assert "clicked" in result


@pytest.mark.asyncio
async def test_click_marker_expired_returns_error():
    """click_marker returns error when map is expired (no screenshot_som called yet)."""
    from luna_mcp.state.marker_map import MarkerMap
    from luna_mcp.tools.som_tools import _make_click_marker

    marker_map = MarkerMap()  # empty/expired

    async def fake_click(x, y): return "ok"
    click_marker = _make_click_marker(marker_map, fake_click)
    result = await click_marker(99)
    assert "error" in result.lower() or "not found" in result.lower()


@pytest.mark.asyncio
async def test_inspect_marker_invokes_diagnose_object():
    """inspect_marker calls diagnose_object with marker's path."""
    from luna_mcp.state.marker_map import MarkerMap, Rect
    from luna_mcp.tools.som_tools import _make_inspect_marker

    marker_map = MarkerMap()
    marker_map.set([Rect(2, "/Canvas/Title", 0, 0, 200, 50, "Text")])

    called_paths = []
    async def fake_diagnose(path):
        called_paths.append(path)
        return f"diag: {path}"

    inspect_marker = _make_inspect_marker(marker_map, fake_diagnose)
    result = await inspect_marker(2)
    assert called_paths == ["/Canvas/Title"]
    assert "diag" in result


@pytest.mark.asyncio
async def test_inspect_marker_not_found():
    from luna_mcp.state.marker_map import MarkerMap
    from luna_mcp.tools.som_tools import _make_inspect_marker

    marker_map = MarkerMap()
    async def fake_diagnose(path): return "ok"
    inspect_marker = _make_inspect_marker(marker_map, fake_diagnose)
    result = await inspect_marker(99)
    assert "error" in result.lower() or "not found" in result.lower()


def test_list_markers_compact_format():
    """list_markers returns compact numbered list."""
    from luna_mcp.state.marker_map import MarkerMap, Rect
    from luna_mcp.tools.som_tools import _list_markers_text

    marker_map = MarkerMap()
    marker_map.set([
        Rect(1, "/Canvas/Btn", 0, 0, 100, 40, "Button"),
        Rect(2, "/Canvas/Title", 0, 50, 200, 30, "Text"),
    ])
    result = _list_markers_text(marker_map)
    assert "1" in result and "Btn" in result
    assert "2" in result and "Title" in result
    assert "Button" in result


# ── m6: overlay legend strips HTML chars ─────────────────────────────────────

def test_overlay_legend_strips_html_chars():
    """_leaf must strip < > \\ from path component (defense-in-depth)."""
    from luna_mcp.som.overlay import _leaf
    name = "<script>x</script>"
    result = _leaf(f"/Canvas/{name}")
    assert "<" not in result
    assert ">" not in result
    assert "\\" not in result
