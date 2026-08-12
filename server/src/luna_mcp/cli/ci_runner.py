"""Headless-Chrome CI orchestrator — fully injectable deps for testability."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RunResult:
    exit_code: int            # 0=all-pass, 1=any-fail, 2=launch-error
    cases: list[dict] = field(default_factory=list)
    failures: int = 0
    errors: int = 0


class CIRunner:
    """Orchestrates: launch Chrome → poll ready → run baselines → collect results.

    All external actions are injected so tests run without real Chrome.
    """

    def __init__(self, launch_fn: Callable, dispatch_fn: Callable,
                 poll_fn: Callable | None = None):
        """
        launch_fn(chrome_bin, port, build_path) -> process
        dispatch_fn(baseline_name, build_path=...) -> str result
        poll_fn(port, timeout) -> bool  (True if port ready)
        """
        self._launch = launch_fn
        self._dispatch = dispatch_fn
        self._poll = poll_fn or _default_poll

    async def run(self, *, baselines: list[str], build_path: str,
                  chrome_bin: str, port: int, timeout: int) -> RunResult:
        # Launch Chrome
        proc = None
        try:
            proc = await self._launch(chrome_bin, port, build_path)
        except Exception as exc:
            return RunResult(exit_code=2, errors=1,
                             cases=[{"name": "launch", "kind": "error",
                                     "message": str(exc)}])

        try:
            # Poll until ready
            ready = await self._poll(port, timeout)
            if not ready:
                return RunResult(exit_code=2, errors=1,
                                 cases=[{"name": "poll_timeout", "kind": "error",
                                         "message": f"port {port} not ready in {timeout}s"}])

            cases = []
            failures = 0
            for name in baselines:
                try:
                    result = await self._dispatch(name, build_path=build_path)
                    passed = "PASS" in str(result).upper() or "MATCH" in str(result).upper()
                    if passed:
                        cases.append({"name": name, "kind": "pass"})
                    else:
                        cases.append({"name": name, "kind": "failure", "message": str(result)})
                        failures += 1
                except Exception as exc:
                    cases.append({"name": name, "kind": "failure", "message": str(exc)})
                    failures += 1

            exit_code = 1 if failures > 0 else 0
            return RunResult(exit_code=exit_code, cases=cases, failures=failures, errors=0)
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()


async def _default_poll(port: int, timeout: int) -> bool:
    """Poll http://localhost:{port}/json until it responds or timeout."""
    import aiohttp
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"http://localhost:{port}/json", timeout=aiohttp.ClientTimeout(total=1)) as r:
                    if r.status == 200:
                        return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False
