"""Tests for template MCP tools."""
from unittest.mock import AsyncMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_template(tmp_path, name, body):
    p = tmp_path / f"{name}.batch"
    p.write_text(body)
    return p


# ── template tool ─────────────────────────────────────────────────────────────

async def test_template_unknown_returns_invalid(tmp_path):
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template"]("nonexistent")
    assert "[INVALID" in result
    assert "not found" in result


async def test_template_expands_and_calls_execute_batch(tmp_path):
    _make_template(tmp_path, "simple", "# params: path\nget_object_detail path={{path}}")
    from luna_mcp.tools.template_tools import _make_tools
    mock_exec = AsyncMock(return_value="detail output")
    with patch("luna_mcp.tools.template_tools.execute_batch", mock_exec):
        tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
        result = await tools["template"]("simple", args="path=/Canvas/Btn")
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0][0]
    assert "get_object_detail path=/Canvas/Btn" in call_args
    assert "via template:simple" in result


async def test_template_strips_header_comments(tmp_path):
    _make_template(tmp_path, "withheader", "# params: path\n# desc: test\nping\nget_hierarchy depth=2")
    mock_exec = AsyncMock(return_value="ok")
    with patch("luna_mcp.tools.template_tools.execute_batch", mock_exec):
        from luna_mcp.tools.template_tools import _make_tools
        tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
        await tools["template"]("withheader", args="path=/x")
    call_args = mock_exec.call_args[0][0]
    assert "# params" not in call_args
    assert "ping" in call_args


async def test_template_missing_arg_returns_invalid(tmp_path):
    _make_template(tmp_path, "needs_path", "get_object_detail path={{path}}")
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template"]("needs_path")  # no args
    assert "[INVALID" in result
    assert "path" in result


async def test_template_appends_via_marker(tmp_path):
    _make_template(tmp_path, "marker_test", "ping")
    mock_exec = AsyncMock(return_value="pong")
    with patch("luna_mcp.tools.template_tools.execute_batch", mock_exec):
        from luna_mcp.tools.template_tools import _make_tools
        tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
        result = await tools["template"]("marker_test")
    assert "[via template:marker_test]" in result


# ── template_list tool ────────────────────────────────────────────────────────

async def test_template_list_empty(tmp_path):
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template_list"]()
    assert "no templates" in result


async def test_template_list_shows_templates(tmp_path):
    _make_template(tmp_path, "check_btn", "# params: path\n# desc: check button\nping")
    _make_template(tmp_path, "audit_tex", "# desc: audit textures\naudit_textures")
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template_list"]()
    assert "check_btn" in result
    assert "audit_tex" in result


async def test_template_list_filter(tmp_path):
    _make_template(tmp_path, "check_install", "ping")
    _make_template(tmp_path, "diagnose_end", "ping")
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template_list"](filter_str="check")
    assert "check_install" in result
    assert "diagnose_end" not in result


# ── template_save tool ────────────────────────────────────────────────────────

async def test_template_save_persists(tmp_path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=user_dir)
    result = await tools["template_save"]("my_workflow", "ping\nget_hierarchy")
    assert "saved" in result
    assert (user_dir / "my_workflow.batch").exists()


async def test_template_save_invalid_name(tmp_path):
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
    result = await tools["template_save"]("bad name!", "ping")
    assert "[INVALID" in result


async def test_template_save_no_overwrite(tmp_path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_template(user_dir, "existing", "old")
    from luna_mcp.tools.template_tools import _make_tools
    tools = _make_tools(bundled_dir=tmp_path, user_dir=user_dir)
    result = await tools["template_save"]("existing", "new")
    assert "[INVALID" in result


async def test_template_args_parsing(tmp_path):
    """parse_args handles quoted values with spaces."""
    _make_template(tmp_path, "q_test", '# params: query\nfind_objects query={{query}}')
    mock_exec = AsyncMock(return_value="found")
    with patch("luna_mcp.tools.template_tools.execute_batch", mock_exec):
        from luna_mcp.tools.template_tools import _make_tools
        tools = _make_tools(bundled_dir=tmp_path, user_dir=tmp_path)
        await tools["template"]("q_test", args='query="Main Camera"')
    call_args = mock_exec.call_args[0][0]
    # value with spaces must be shell-quoted so execute_batch can shlex.split it correctly
    assert "find_objects" in call_args
    assert "query=" in call_args
    # the quoted form: query='Main Camera' or query="Main Camera"
    assert "Main Camera" in call_args
