"""Tests for headless CI runner (cli/ci_runner.py). No real Chrome."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ── helper to run async tests ────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


# ── CIRunner basic flow ──────────────────────────────────────────────────────

def test_ci_runner_all_pass():
    """All baselines pass → exit_code 0, JUnit has 0 failures."""
    from luna_mcp.cli.ci_runner import CIRunner

    async def fake_dispatch(name, **kw):
        return "PASS: baseline matches"

    async def fake_launch(chrome_bin, port, build_path):
        return MagicMock()  # fake process

    runner = CIRunner(launch_fn=fake_launch, dispatch_fn=fake_dispatch,
                      poll_fn=AsyncMock(return_value=True))
    result = _run(runner.run(
        baselines=["a", "b"],
        build_path="/tmp/fake",
        chrome_bin="chrome",
        port=9299,
        timeout=5,
    ))
    assert result.exit_code == 0
    assert result.failures == 0
    assert result.errors == 0
    assert len(result.cases) == 2


def test_ci_runner_some_fail():
    """Some baselines fail → exit_code 1."""
    from luna_mcp.cli.ci_runner import CIRunner

    async def fake_dispatch(name, **kw):
        if name == "b":
            return "FAIL: pixel diff 3.1%"
        return "PASS: ok"

    runner = CIRunner(launch_fn=AsyncMock(return_value=MagicMock()),
                      dispatch_fn=fake_dispatch,
                      poll_fn=AsyncMock(return_value=True))
    result = _run(runner.run(
        baselines=["a", "b"],
        build_path="/tmp/fake",
        chrome_bin="chrome",
        port=9299,
        timeout=5,
    ))
    assert result.exit_code == 1
    assert result.failures == 1


def test_ci_runner_launch_fail():
    """Chrome fails to launch → exit_code 2, single error testcase."""
    from luna_mcp.cli.ci_runner import CIRunner

    async def bad_launch(chrome_bin, port, build_path):
        raise RuntimeError("chrome not found")

    runner = CIRunner(launch_fn=bad_launch,
                      dispatch_fn=AsyncMock(),
                      poll_fn=AsyncMock(return_value=True))
    result = _run(runner.run(
        baselines=["a"],
        build_path="/tmp/fake",
        chrome_bin="chrome",
        port=9299,
        timeout=5,
    ))
    assert result.exit_code == 2
    assert result.errors >= 1


def test_ci_runner_poll_timeout():
    """Port never becomes ready → exit_code 2."""
    from luna_mcp.cli.ci_runner import CIRunner

    runner = CIRunner(launch_fn=AsyncMock(return_value=MagicMock()),
                      dispatch_fn=AsyncMock(),
                      poll_fn=AsyncMock(return_value=False))  # never ready
    result = _run(runner.run(
        baselines=["a"],
        build_path="/tmp/fake",
        chrome_bin="chrome",
        port=9299,
        timeout=1,
    ))
    assert result.exit_code == 2
    assert result.errors >= 1


def test_ci_runner_no_traceback_on_launch_fail():
    """On launch failure, result is structured (no unhandled exception)."""
    from luna_mcp.cli.ci_runner import CIRunner

    async def bad_launch(*a, **kw):
        raise OSError("no such file")

    runner = CIRunner(launch_fn=bad_launch,
                      dispatch_fn=AsyncMock(),
                      poll_fn=AsyncMock(return_value=True))
    # Should not raise
    result = _run(runner.run(
        baselines=[],
        build_path="/tmp/fake",
        chrome_bin="nonexistent",
        port=9299,
        timeout=5,
    ))
    assert result.exit_code == 2


def test_ci_runner_subprocess_shell_false():
    """Real launch_fn in ci.py builds Popen call with shell=False."""
    from luna_mcp.cli.ci import _make_launch_fn
    calls = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            calls.append((cmd, kw))

    with patch("luna_mcp.cli.ci.subprocess.Popen", FakePopen):
        launch_fn = _make_launch_fn()

        async def do():
            await launch_fn("chrome", 9299, "/tmp/build")

        _run(do())

    assert calls, "Popen never called"
    cmd, kw = calls[0]
    assert isinstance(cmd, list), "cmd must be a list (shell=False)"
    assert kw.get("shell") is not True


# ── C1: Chrome process must be terminated on both paths ──────────────────────

def test_ci_runner_terminate_called_on_all_pass():
    """C1: proc.terminate() must be called when all baselines pass."""
    from luna_mcp.cli.ci_runner import CIRunner

    proc = MagicMock()
    proc.wait = MagicMock(return_value=None)

    async def fake_launch(chrome_bin, port, build_path):
        return proc

    runner = CIRunner(launch_fn=fake_launch,
                      dispatch_fn=AsyncMock(return_value="PASS: ok"),
                      poll_fn=AsyncMock(return_value=True))
    _run(runner.run(baselines=["a"], build_path="/tmp/fake",
                    chrome_bin="chrome", port=9299, timeout=5))
    proc.terminate.assert_called_once()


def test_ci_runner_terminate_called_on_poll_timeout():
    """C1: proc.terminate() must be called even when poll times out."""
    from luna_mcp.cli.ci_runner import CIRunner

    proc = MagicMock()
    proc.wait = MagicMock(return_value=None)

    async def fake_launch(chrome_bin, port, build_path):
        return proc

    runner = CIRunner(launch_fn=fake_launch,
                      dispatch_fn=AsyncMock(),
                      poll_fn=AsyncMock(return_value=False))
    _run(runner.run(baselines=["a"], build_path="/tmp/fake",
                    chrome_bin="chrome", port=9299, timeout=1))
    proc.terminate.assert_called_once()


# ── M2: _default_poll must use get_running_loop(), not get_event_loop() ───────

def test_default_poll_returns_true_on_200():
    """M2: _default_poll returns True when server responds 200."""
    from unittest.mock import AsyncMock as _AM
    from unittest.mock import MagicMock as _MM
    from unittest.mock import patch as _patch

    async def _run_poll():
        from luna_mcp.cli.ci_runner import _default_poll

        mock_resp = _MM()
        mock_resp.status = 200
        mock_resp.__aenter__ = _AM(return_value=mock_resp)
        mock_resp.__aexit__ = _AM(return_value=False)

        mock_get = _MM()
        mock_get.__aenter__ = _AM(return_value=mock_resp)
        mock_get.__aexit__ = _AM(return_value=False)

        mock_session = _MM()
        mock_session.get = _MM(return_value=mock_get)
        mock_session.__aenter__ = _AM(return_value=mock_session)
        mock_session.__aexit__ = _AM(return_value=False)

        with _patch("aiohttp.ClientSession", return_value=mock_session):
            return await _default_poll(9299, 2)

    result = asyncio.run(_run_poll())
    assert result is True


def test_default_poll_returns_false_after_deadline():
    """M2: _default_poll returns False when deadline passes without 200."""
    async def _run_poll():
        from unittest.mock import AsyncMock as _AM
        from unittest.mock import MagicMock as _MM
        from unittest.mock import patch as _patch

        from luna_mcp.cli.ci_runner import _default_poll

        mock_session = _MM()
        mock_session.__aenter__ = _AM(return_value=mock_session)
        mock_session.__aexit__ = _AM(return_value=False)
        mock_session.get = _MM(side_effect=Exception("connection refused"))

        with _patch("aiohttp.ClientSession", return_value=mock_session):
            # timeout=0 → deadline already passed → must return False quickly
            return await _default_poll(9299, 0)

    result = asyncio.run(_run_poll())
    assert result is False


# ── M3: _make_launch_fn appends file:// URL when build_path given ────────────

def test_make_launch_fn_appends_file_url_when_build_path():
    """M3: cmd must include file:// URL when build_path is non-empty."""
    import os

    from luna_mcp.cli.ci import _make_launch_fn

    captured_cmds = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            captured_cmds.append(cmd)
            self.terminate = MagicMock()
            self.wait = MagicMock()

    with patch("luna_mcp.cli.ci.subprocess.Popen", FakePopen):
        launch_fn = _make_launch_fn()

        async def do():
            return await launch_fn("chrome", 9299, "/tmp/build")

        _run(do())

    assert captured_cmds, "Popen never called"
    cmd = captured_cmds[0]
    url_args = [a for a in cmd if a.startswith("file://")]
    assert url_args, f"No file:// URL in cmd: {cmd}"
    expected = f"file://{os.path.abspath('/tmp/build')}"
    assert url_args[0] == expected


def test_make_launch_fn_no_url_when_empty_build_path():
    """M3: cmd must NOT include file:// URL when build_path is empty."""
    from luna_mcp.cli.ci import _make_launch_fn

    captured_cmds = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            captured_cmds.append(cmd)
            self.terminate = MagicMock()
            self.wait = MagicMock()

    with patch("luna_mcp.cli.ci.subprocess.Popen", FakePopen):
        launch_fn = _make_launch_fn()

        async def do():
            return await launch_fn("chrome", 9299, "")

        _run(do())

    cmd = captured_cmds[0]
    url_args = [a for a in cmd if a.startswith("file://")]
    assert not url_args, f"Unexpected file:// URL in cmd: {cmd}"
