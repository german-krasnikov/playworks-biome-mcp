"""TDD tests for SamplingService (luna playable ad visual LLM)."""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ── SamplingService tests ────────────────────────────────────────────────────

def test_disabled_returns_none(monkeypatch):
    """enabled=False when LUNA_VISUAL_LLM != '1'."""
    monkeypatch.delenv("LUNA_VISUAL_LLM", raising=False)
    from luna_mcp.sampling import SamplingService
    svc = SamplingService()
    assert svc.enabled is False


def test_enabled_with_env(monkeypatch, tmp_path):
    """enabled=True only when LUNA_VISUAL_LLM=1 and claude CLI exists."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    with patch("shutil.which", return_value="/usr/local/bin/claude"):
        from luna_mcp.sampling import SamplingService
        svc = SamplingService()
        assert svc.enabled is True


def test_enabled_false_when_no_cli(monkeypatch):
    """enabled=False even if LUNA_VISUAL_LLM=1 but claude not in PATH."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    with patch("shutil.which", return_value=None):
        from luna_mcp.sampling import SamplingService
        svc = SamplingService()
        assert svc.enabled is False


@pytest.mark.asyncio
async def test_subprocess_spawned_with_haiku(monkeypatch, tmp_path):
    """_run spawns claude with --model haiku."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    png = tmp_path / "shot.png"
    png.write_bytes(b"\x89PNG")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"PASS: looks correct", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)) as mock_exec:
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        result = await svc.describe_image("What is this?", str(png))

    call_args = mock_exec.call_args[0]
    assert "--model" in call_args
    idx = list(call_args).index("--model")
    assert call_args[idx + 1] == "haiku"


@pytest.mark.asyncio
async def test_timeout_kills_process(monkeypatch, tmp_path):
    """Process is killed on timeout, returns None."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.returncode = None
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_proc)):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        result = await svc._run(["claude", "-p", "test"], timeout=0.01)

    assert result is None
    mock_proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_concurrency_semaphore(monkeypatch):
    """At most 4 concurrent subprocess calls."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")

    concurrent_max = 0
    concurrent_now = 0
    lock = asyncio.Lock()

    async def fake_communicate():
        nonlocal concurrent_max, concurrent_now
        async with lock:
            concurrent_now += 1
            if concurrent_now > concurrent_max:
                concurrent_max = concurrent_now
        await asyncio.sleep(0.05)
        async with lock:
            concurrent_now -= 1
        return (b"ok", b"")

    def make_proc():
        p = MagicMock()
        p.communicate = fake_communicate
        p.returncode = 0
        p.kill = Mock()
        p.wait = AsyncMock(return_value=0)
        return p

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=lambda *a, **kw: make_proc())):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        svc._semaphore = None  # reset class-level semaphore

        tasks = [svc._run(["claude", "-p", "x"], timeout=5.0) for _ in range(10)]
        await asyncio.gather(*tasks)

    assert concurrent_max <= 4


# ── sampling_postproc tests ──────────────────────────────────────────────────

def test_refusal_normalized_to_none():
    from luna_mcp.sampling_postproc import normalize
    result, is_refusal = normalize("I cannot analyze this image.")
    assert result is None
    assert is_refusal is True


def test_fence_stripped():
    from luna_mcp.sampling_postproc import strip_fences
    assert strip_fences("```\nPASS: button visible\n```") == "PASS: button visible"


def test_screenshot_path_passed_as_arg(monkeypatch, tmp_path):
    """PNG path appears as last positional arg to subprocess."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    png = tmp_path / "test.png"
    png.write_bytes(b"\x89PNG")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"PASS", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured = []

    async def capture(*args, **kwargs):
        captured.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        asyncio.run(svc.describe_image("describe", str(png)))

    assert str(png) in captured


@pytest.mark.asyncio
async def test_diff_passes_two_images(monkeypatch, tmp_path):
    """verify_visual_diff passes before and after paths to subprocess."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    before.write_bytes(b"\x89PNG")
    after.write_bytes(b"\x89PNG")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"button appeared", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured = []

    async def capture(*args, **kwargs):
        captured.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        result = await svc.verify_visual_diff(str(before), str(after), "what changed?")

    assert str(before) in captured
    assert str(after) in captured
    assert result == "button appeared"


@pytest.mark.asyncio
async def test_tool_degraded_when_disabled(monkeypatch):
    """analyze_screenshot returns DEGRADED message when SamplingService disabled."""
    monkeypatch.delenv("LUNA_VISUAL_LLM", raising=False)

    from luna_mcp.sampling import SamplingService
    svc = SamplingService()
    assert not svc.enabled

    mock_bridge = MagicMock()
    mock_bridge.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")

    from mcp.server.fastmcp import FastMCP

    from luna_mcp.tools.llm_tools import register_llm_tools
    mock_mcp = FastMCP("test")
    tools = register_llm_tools(mock_mcp, svc, lambda: mock_bridge, exposed=set())

    analyze_fn = tools["analyze_screenshot"][0]
    result = await analyze_fn()
    assert "DEGRADED" in result
    assert "LUNA_VISUAL_LLM" in result


# ── M3: compare_screenshots path validation ───────────────────────────────────

@pytest.mark.asyncio
async def test_compare_screenshots_rejects_etc_passwd(monkeypatch):
    """compare_screenshots with /etc/passwd path must return [INVALID: ...], not subprocess (M3)."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")

    from mcp.server.fastmcp import FastMCP

    from luna_mcp.sampling import SamplingService
    from luna_mcp.tools.llm_tools import register_llm_tools

    svc = MagicMock(spec=SamplingService)
    svc.enabled = True
    svc.verify_visual_diff = AsyncMock(return_value="diff result")

    mock_mcp = FastMCP("test")
    tools = register_llm_tools(mock_mcp, svc, lambda: None, exposed=set())
    compare_fn = tools["compare_screenshots"][0]

    result = await compare_fn(
        before_path="/etc/passwd",
        after_path="/etc/passwd",
        what_changed="test",
    )
    assert "[INVALID" in result
    svc.verify_visual_diff.assert_not_called()


@pytest.mark.asyncio
async def test_compare_screenshots_rejects_nonexistent_tmp_path(monkeypatch, tmp_path):
    """compare_screenshots with non-existent file under /tmp returns [INVALID: file not found]."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")

    from mcp.server.fastmcp import FastMCP

    from luna_mcp.sampling import SamplingService
    from luna_mcp.tools.llm_tools import register_llm_tools

    svc = MagicMock(spec=SamplingService)
    svc.enabled = True
    svc.verify_visual_diff = AsyncMock(return_value="diff result")

    mock_mcp = FastMCP("test")
    tools = register_llm_tools(mock_mcp, svc, lambda: None, exposed=set())
    compare_fn = tools["compare_screenshots"][0]

    import tempfile
    fake = os.path.join(tempfile.gettempdir(), "luna_nonexistent_xyz.png")
    result = await compare_fn(
        before_path=fake,
        after_path=fake,
        what_changed="test",
    )
    assert "[INVALID" in result
    svc.verify_visual_diff.assert_not_called()


# ── m1: atexit cleanup kills active processes ─────────────────────────────────

def test_atexit_cleanup_kills_active_processes():
    """_cleanup_subprocesses kills all procs in _active_procs and is registered with atexit."""
    import atexit
    import importlib
    from unittest.mock import MagicMock

    from luna_mcp import sampling as smod
    importlib.reload(smod)

    mock_proc = MagicMock()
    mock_proc.returncode = None  # still running

    smod._active_procs.add(mock_proc)
    smod._cleanup_subprocesses()
    mock_proc.kill.assert_called_once()

    # Verify registered with atexit
    try:
        handlers = [h[0] for h in atexit._exithandlers]
        assert smod._cleanup_subprocesses in handlers
    except AttributeError:
        pass  # non-CPython
