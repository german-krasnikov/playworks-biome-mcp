"""Phase 17: Static Build Analyzer -- TDD tests.

Tools read Luna build files from disk. No Chrome/CDP needed.
"""
import json

import pytest

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def build_dir(tmp_path):
    """Create a minimal mock Luna build directory."""
    stage4 = tmp_path / "LunaTemp" / "stage4" / "develop"
    stage3 = tmp_path / "LunaTemp" / "stage3"
    stage4.mkdir(parents=True)
    stage3.mkdir(parents=True)

    # luna.json
    (stage4 / "luna.json").write_text(json.dumps({
        "version": "7.1.0",
        "platform": "ironSource",
    }))

    # JS files
    js_dir = stage4 / "js"
    js_dir.mkdir()
    (js_dir / "UnityScriptsCompiler.js").write_bytes(b"x" * 1024 * 500)  # 500 KB
    (js_dir / "TextMeshPro.js").write_bytes(b"x" * 1024 * 2341)          # 2341 KB
    (js_dir / "bridge.js").write_bytes(b"x" * 1024 * 100)               # 100 KB

    # playground.json
    playground = {
        "fields": {
            "GameManager": {
                "playerSpeed": {
                    "type": "float",
                    "defaultValue": 1.0,
                    "title": "Player Speed",
                    "section": "Gameplay",
                },
                "timeScale": {
                    "type": "float",
                    "defaultValue": 1.0,
                    "title": "Time Scale",
                    "section": "",
                },
            }
        }
    }
    (js_dir / "playground.json").write_text(json.dumps(playground))

    # textures
    tex_dir = stage4 / "assets" / "textures"
    tex_dir.mkdir(parents=True)
    (tex_dir / "corn.png").write_bytes(b"x" * 1024 * 49)
    (tex_dir / "wheat.png").write_bytes(b"x" * 1024 * 43)

    # shaders
    assets_dir = stage4 / "assets"
    shaders = ["void main(){gl_FragColor=vec4(1.0);}" for _ in range(5)]
    (assets_dir / "shaders.json").write_text(json.dumps(shaders))

    # stats.json in stage3
    stats = {
        "types": [
            {
                "assets": [
                    {"title": "LiberationSans SDF", "path": "Assets/TextMesh Pro/LiberationSans.asset", "size": 201 * 1024},
                    {"title": "corn", "path": "Assets/Samples/corn.png", "size": 49 * 1024},
                    {"title": "small", "path": "Assets/tiny.png", "size": 5 * 1024},
                ]
            }
        ]
    }
    (stage3 / "stats.json").write_text(json.dumps(stats))

    return str(tmp_path)


@pytest.fixture
def empty_dir(tmp_path):
    """Build dir with only LunaTemp (no files inside)."""
    (tmp_path / "LunaTemp").mkdir()
    return str(tmp_path)


# ── analyze_build ────────────────────────────────────────────────────────────

async def test_analyze_build_header(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "BUILD ANALYSIS:" in result
    assert build_dir in result


async def test_analyze_build_platform_and_sdk(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "ironSource" in result
    assert "7.1.0" in result


async def test_analyze_build_size_breakdown(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "SIZE BREAKDOWN" in result
    assert "Scripts" in result
    assert "Textures" in result


async def test_analyze_build_flags_textmeshpro(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "TextMeshPro" in result
    assert "[!!" in result  # warning marker


async def test_analyze_build_playground_fields(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "PLAYGROUND FIELDS" in result
    assert "playerSpeed" in result


async def test_analyze_build_shaders(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "SHADERS" in result
    assert "5 compiled" in result


async def test_analyze_build_recommendations(build_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(build_dir)
    assert "RECOMMENDATIONS" in result


async def test_analyze_build_missing_luna_temp(tmp_path):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(str(tmp_path))
    assert "error" in result.lower()


async def test_analyze_build_partial_build(empty_dir):
    from luna_mcp.tools.build_tools import analyze_build
    result = await analyze_build(empty_dir)
    # Should not crash, partial info returned
    assert "BUILD ANALYSIS" in result or "error" in result.lower()


# ── get_playground_fields ────────────────────────────────────────────────────

async def test_get_playground_fields_returns_fields(build_dir):
    from luna_mcp.tools.build_tools import get_playground_fields
    result = await get_playground_fields(build_dir)
    assert "PLAYGROUND FIELDS" in result
    assert "playerSpeed" in result
    assert "float" in result
    assert "Player Speed" in result


async def test_get_playground_fields_section(build_dir):
    from luna_mcp.tools.build_tools import get_playground_fields
    result = await get_playground_fields(build_dir)
    assert "Gameplay" in result


async def test_get_playground_fields_missing_file(tmp_path):
    from luna_mcp.tools.build_tools import get_playground_fields
    result = await get_playground_fields(str(tmp_path))
    assert "not found" in result.lower() or "error" in result.lower() or "no playground" in result.lower()


async def test_get_playground_fields_no_fields(tmp_path):
    stage4 = tmp_path / "LunaTemp" / "stage4" / "develop" / "js"
    stage4.mkdir(parents=True)
    (stage4 / "playground.json").write_text(json.dumps({"fields": {}}))
    from luna_mcp.tools.build_tools import get_playground_fields
    result = await get_playground_fields(str(tmp_path))
    assert "0" in result or "no fields" in result.lower() or "PLAYGROUND FIELDS" in result


# ── get_build_assets ─────────────────────────────────────────────────────────

async def test_get_build_assets_returns_sorted(build_dir):
    from luna_mcp.tools.build_tools import get_build_assets
    result = await get_build_assets(build_dir)
    assert "ASSETS" in result
    assert "LiberationSans" in result
    assert "corn" in result
    # LiberationSans (201KB) should appear before corn (49KB)
    assert result.index("LiberationSans") < result.index("corn")


async def test_get_build_assets_min_size_filter(build_dir):
    from luna_mcp.tools.build_tools import get_build_assets
    result = await get_build_assets(build_dir, min_size_kb=100)
    assert "LiberationSans" in result
    assert "corn" not in result  # 49KB < 100KB


async def test_get_build_assets_missing_stats(tmp_path):
    from luna_mcp.tools.build_tools import get_build_assets
    result = await get_build_assets(str(tmp_path))
    assert "stats.json" in result.lower() or "error" in result.lower() or "no assets" in result.lower()


async def test_get_build_assets_default_threshold(build_dir):
    """Default min_size_kb=10, should exclude 5KB asset."""
    from luna_mcp.tools.build_tools import get_build_assets
    result = await get_build_assets(build_dir)
    assert "small" not in result  # 5KB < 10KB


# ── batch registration ───────────────────────────────────────────────────────

def test_tools_registered_for_batch():
    import luna_mcp.server  # noqa: F401 — triggers registration
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    assert "analyze_build" in _TOOL_REGISTRY
    assert "get_playground_fields" in _TOOL_REGISTRY
    assert "get_build_assets" in _TOOL_REGISTRY
