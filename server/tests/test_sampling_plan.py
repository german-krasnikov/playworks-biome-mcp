"""TDD: SamplingService.plan() method."""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_plan_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("LUNA_VISUAL_LLM", raising=False)
    from luna_mcp.sampling import SamplingService
    svc = SamplingService()
    result = await svc.plan("do something", "system prompt")
    assert result is None


@pytest.mark.asyncio
async def test_plan_calls_run_without_image(monkeypatch):
    """plan() must NOT pass image_path arg to subprocess."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"find_objects query=CTA", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        result = await svc.plan("find CTA", "you are a planner")

    # No PNG path in args
    assert not any(str(a).endswith(".png") for a in captured_args)
    assert result == "find_objects query=CTA"


@pytest.mark.asyncio
async def test_plan_passes_full_prompt(monkeypatch):
    """plan() combines system_prompt + intent into prompt text."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"ping", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        await svc.plan("my_intent_text", "my_system_prompt")

    # The combined prompt string must contain both intent and system
    prompt_arg = next((a for a in captured_args if isinstance(a, str) and "my_system_prompt" in a), None)
    assert prompt_arg is not None
    assert "my_intent_text" in prompt_arg


@pytest.mark.asyncio
async def test_plan_with_ctx_appends(monkeypatch):
    """When ctx is non-empty, it's appended to the prompt."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"ping", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        await svc.plan("intent", "system", ctx="extra_context_xyz")

    prompt_arg = next((a for a in captured_args if isinstance(a, str) and "extra_context_xyz" in a), None)
    assert prompt_arg is not None


@pytest.mark.asyncio
async def test_plan_without_ctx_no_context_section(monkeypatch):
    """When ctx='', no CONTEXT section is added."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"ping", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=capture):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        await svc.plan("intent", "system", ctx="")

    prompt_arg = next((a for a in captured_args if isinstance(a, str) and "intent" in a), None)
    assert prompt_arg is not None
    assert "CONTEXT" not in prompt_arg
