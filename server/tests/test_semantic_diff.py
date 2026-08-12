"""Tests for build_diff/semantic_diff.py — RED phase."""
import pytest

from luna_mcp.build_diff.semantic_diff import CHUNK_SIZE, SemanticDiff


class _MockSampling:
    """Fake sampling: enabled, returns fixed summary."""
    enabled = True

    def __init__(self, result="summarized change"):
        self._result = result
        self.calls = []

    async def plan(self, prompt: str, system_prompt: str) -> str:
        self.calls.append(prompt)
        return self._result


class _DisabledSampling:
    enabled = False

    async def plan(self, prompt, system_prompt):
        raise AssertionError("should not be called")


@pytest.mark.asyncio
async def test_diff_identical_files_returns_none(tmp_path):
    a = tmp_path / "a.js"; a.write_text("same content")
    b = tmp_path / "b.js"; b.write_text("same content")
    sd = SemanticDiff(_MockSampling())
    result = await sd.diff_text_file(a, b, "main.js")
    assert result is None


@pytest.mark.asyncio
async def test_diff_different_files_returns_summary(tmp_path):
    a = tmp_path / "a.js"; a.write_text("function old() {}")
    b = tmp_path / "b.js"; b.write_text("function new_version() {}")
    mock = _MockSampling("renamed function")
    sd = SemanticDiff(mock)
    result = await sd.diff_text_file(a, b, "main.js")
    assert result == "renamed function"
    assert len(mock.calls) == 1


@pytest.mark.asyncio
async def test_diff_disabled_sampling_returns_none(tmp_path):
    a = tmp_path / "a.js"; a.write_text("old")
    b = tmp_path / "b.js"; b.write_text("new")
    sd = SemanticDiff(_DisabledSampling())
    result = await sd.diff_text_file(a, b, "main.js")
    assert result is None


@pytest.mark.asyncio
async def test_diff_none_sampling_returns_none(tmp_path):
    a = tmp_path / "a.js"; a.write_text("old")
    b = tmp_path / "b.js"; b.write_text("new")
    sd = SemanticDiff(None)
    result = await sd.diff_text_file(a, b, "main.js")
    assert result is None


@pytest.mark.asyncio
async def test_diff_large_file_truncates(tmp_path):
    """If diff > CHUNK_SIZE, should still return a summary (truncated)."""
    big = "x" * (CHUNK_SIZE + 1000)
    a = tmp_path / "a.js"; a.write_text("A\n" * 5000)
    b = tmp_path / "b.js"; b.write_text("B\n" * 5000)
    mock = _MockSampling("big diff")
    sd = SemanticDiff(mock)
    result = await sd.diff_text_file(a, b, "large.js")
    assert result is not None
    assert len(mock.calls) >= 1


@pytest.mark.asyncio
async def test_diff_sampling_failure_returns_fallback(tmp_path):
    a = tmp_path / "a.js"; a.write_text("old")
    b = tmp_path / "b.js"; b.write_text("new")

    class _FailSampling:
        enabled = True
        async def plan(self, p, s):
            raise RuntimeError("API down")

    sd = SemanticDiff(_FailSampling())
    # Should not raise — returns None or a fallback string
    result = await sd.diff_text_file(a, b, "main.js")
    # None is acceptable fallback
    assert result is None or isinstance(result, str)


@pytest.mark.asyncio
async def test_diff_nonexistent_file_returns_error(tmp_path):
    a = tmp_path / "missing.js"  # does not exist
    b = tmp_path / "b.js"; b.write_text("new")
    sd = SemanticDiff(_MockSampling())
    result = await sd.diff_text_file(a, b, "missing.js")
    assert result is None or "error" in str(result).lower()


@pytest.mark.asyncio
async def test_diff_passes_filepath_in_prompt(tmp_path):
    a = tmp_path / "a.js"; a.write_text("old")
    b = tmp_path / "b.js"; b.write_text("new")
    mock = _MockSampling("ok")
    sd = SemanticDiff(mock)
    await sd.diff_text_file(a, b, "src/game/Player.js")
    assert any("src/game/Player.js" in call for call in mock.calls)


@pytest.mark.asyncio
async def test_chunk_size_constant_is_positive():
    assert CHUNK_SIZE > 0
    assert isinstance(CHUNK_SIZE, int)
