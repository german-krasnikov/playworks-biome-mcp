"""TDD tests for SamplingService.describe_image_multi."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_describe_image_multi_disabled_returns_none(monkeypatch):
    """Returns None when sampling disabled."""
    monkeypatch.delenv("LUNA_VISUAL_LLM", raising=False)
    from luna_mcp.sampling import SamplingService
    svc = SamplingService()
    result = await svc.describe_image_multi("prompt", ["/tmp/a.png"])
    assert result is None


@pytest.mark.asyncio
async def test_describe_image_multi_empty_paths_returns_none(monkeypatch):
    """Returns None for empty image list."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    with patch("shutil.which", return_value="/usr/bin/claude"):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        result = await svc.describe_image_multi("prompt", [])
    assert result is None


@pytest.mark.asyncio
async def test_describe_image_multi_passes_all_images_to_subprocess(monkeypatch, tmp_path):
    """All image paths appear in subprocess args."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    img1 = tmp_path / "a.png"
    img2 = tmp_path / "b.png"
    img1.write_bytes(b"\x89PNG")
    img2.write_bytes(b"\x89PNG")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"motion result", b""))
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
        result = await svc.describe_image_multi("describe motion", [str(img1), str(img2)])

    assert str(img1) in captured_args
    assert str(img2) in captured_args
    assert result == "motion result"


@pytest.mark.asyncio
async def test_describe_image_multi_uses_haiku_model(monkeypatch, tmp_path):
    """--model haiku appears in subprocess args."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    img = tmp_path / "frame.png"
    img.write_bytes(b"\x89PNG")

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"bouncing", b""))
    mock_proc.returncode = 0
    mock_proc.kill = Mock()
    mock_proc.wait = AsyncMock(return_value=0)

    captured = []

    async def cap(*args, **kwargs):
        captured.extend(args)
        return mock_proc

    with patch("shutil.which", return_value="/usr/bin/claude"), \
         patch("asyncio.create_subprocess_exec", new=cap):
        import importlib

        from luna_mcp import sampling as smod
        importlib.reload(smod)
        svc = smod.SamplingService()
        await svc.describe_image_multi("test", [str(img)])

    assert "--model" in captured
    idx = list(captured).index("--model")
    assert captured[idx + 1] == "haiku"


@pytest.mark.asyncio
async def test_describe_image_multi_concurrency_semaphore(monkeypatch):
    """Concurrency limited by semaphore (≤4 concurrent)."""
    monkeypatch.setenv("LUNA_VISUAL_LLM", "1")
    monkeypatch.setenv("LUNA_VISUAL_CONCURRENCY", "4")

    concurrent_max = 0
    concurrent_now = 0
    lock = asyncio.Lock()

    async def fake_communicate():
        nonlocal concurrent_max, concurrent_now
        async with lock:
            concurrent_now += 1
            if concurrent_now > concurrent_max:
                concurrent_max = concurrent_now
        await asyncio.sleep(0.02)
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
        svc._semaphore = None  # reset

        tasks = [svc.describe_image_multi("p", ["/tmp/x.png"]) for _ in range(8)]
        await asyncio.gather(*tasks)

    assert concurrent_max <= 4
