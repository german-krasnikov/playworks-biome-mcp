"""Phase 18: tool consolidation tests."""
from unittest.mock import Mock


def test_maybe_expose_registers_when_in_set():
    from luna_mcp.tools import maybe_expose
    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    async def my_tool(): pass
    maybe_expose(mock_mcp, my_tool, {"my_tool"})
    mock_mcp.tool.assert_called_once()


def test_maybe_expose_skips_when_not_in_set():
    from luna_mcp.tools import maybe_expose
    mock_mcp = Mock()
    async def my_tool(): pass
    maybe_expose(mock_mcp, my_tool, {"other_tool"})
    mock_mcp.tool.assert_not_called()


def test_maybe_expose_name_override():
    from luna_mcp.tools import maybe_expose
    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    async def analyze_build_tool(): pass
    maybe_expose(mock_mcp, analyze_build_tool, {"analyze_build"}, name="analyze_build")
    mock_mcp.tool.assert_called_once()


def test_exposed_tools_constant_exists():
    from luna_mcp.wiring import EXPOSED_TOOLS
    assert isinstance(EXPOSED_TOOLS, (set, frozenset))
    assert len(EXPOSED_TOOLS) == 112  # 106 + 6 Sprint-6 (3 probes + get_playground_fields + set_playground_field + step_frame)


def test_batch_only_tools_still_importable():
    """All tools must remain importable from server module."""
    from luna_mcp.server import get_enums, get_layers, simulate_click, trigger_gc
    assert callable(get_layers)
    assert callable(simulate_click)
    assert callable(trigger_gc)
    assert callable(get_enums)


def test_all_tools_in_batch_registry():
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    # Must have at least 85 tools (84 from modules + ping)
    assert len(_TOOL_REGISTRY) >= 85, f"Batch registry has {len(_TOOL_REGISTRY)} tools, expected >=85"


def test_maybe_expose_read_only_default():
    """Default read_only=True passes readOnlyHint annotation when available."""
    from luna_mcp.tools import _HAS_ANNOTATIONS, maybe_expose
    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    async def my_tool(): pass
    maybe_expose(mock_mcp, my_tool, {"my_tool"})
    mock_mcp.tool.assert_called_once()
    if _HAS_ANNOTATIONS:
        kwargs = mock_mcp.tool.call_args[1]
        ann = kwargs.get("annotations")
        assert ann is not None
        assert ann.readOnlyHint is True


def test_maybe_expose_mutation():
    """read_only=False passes destructiveHint annotation when available."""
    from luna_mcp.tools import _HAS_ANNOTATIONS, maybe_expose
    mock_mcp = Mock()
    mock_mcp.tool.return_value = lambda fn: fn
    async def my_tool(): pass
    maybe_expose(mock_mcp, my_tool, {"my_tool"}, read_only=False)
    mock_mcp.tool.assert_called_once()
    if _HAS_ANNOTATIONS:
        kwargs = mock_mcp.tool.call_args[1]
        ann = kwargs.get("annotations")
        assert ann is not None
        assert ann.readOnlyHint is False
        assert ann.destructiveHint is True


def test_batch_only_sample_in_registry():
    """Specific batch-only tools must be in batch registry."""
    from luna_mcp.tools.batch import _TOOL_REGISTRY
    batch_only = [
        "get_layers", "get_game_state", "toggle_editor_camera",
        "simulate_click", "simulate_touch", "simulate_key",
        "trigger_gc", "get_enums", "get_type_info", "get_assemblies",
        "raycast", "get_canvas_info", "get_audio_sources",
        "snapshot_state", "restore_state", "watch_property",
        "get_render_stats", "get_vram_usage", "get_gpu_info",
    ]
    for name in batch_only:
        assert name in _TOOL_REGISTRY, f"{name} missing from batch registry"
