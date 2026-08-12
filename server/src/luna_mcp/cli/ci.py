"""Headless CI entrypoint: python -m luna_mcp.cli.ci"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys

from .ci_runner import CIRunner, _default_poll
from .junit import JUnitWriter


def _make_launch_fn():
    """Return a coroutine factory that launches Chrome via subprocess (shell=False).

    Returns the Popen handle so callers can terminate Chrome on exit.
    """
    async def launch(chrome_bin: str, port: int, build_path: str) -> subprocess.Popen:
        cmd = [
            chrome_bin,
            "--headless=new",
            f"--remote-debugging-port={port}",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir=/tmp/luna_ci_{port}",
        ]
        if build_path:
            cmd.append(f"file://{os.path.abspath(build_path)}")
        return subprocess.Popen(cmd, shell=False, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    return launch


def _make_dispatch_fn(tool_registry: dict):
    """Dispatch baseline checks via the batch registry."""
    async def dispatch(name: str, build_path: str = ""):
        fn, _ = tool_registry.get("visual_baseline_check", (None, None))
        if fn is None:
            return "FAIL: visual_baseline_check not found"
        return await fn(name=name)
    return dispatch


def main():
    parser = argparse.ArgumentParser(description="Playworks Biome headless CI runner")
    parser.add_argument("--baselines", required=True,
                        help="Comma-separated baseline names")
    parser.add_argument("--build-path", default="", help="Build path")
    parser.add_argument("--chrome-bin", default=os.environ.get("LUNA_CHROME_BIN", "google-chrome"))
    parser.add_argument("--port", type=int, default=9299)
    parser.add_argument("--junit", default="", help="Output JUnit XML path")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    from luna_mcp.tools.batch import _TOOL_REGISTRY
    baselines = [b.strip() for b in args.baselines.split(",") if b.strip()]

    runner = CIRunner(
        launch_fn=_make_launch_fn(),
        dispatch_fn=_make_dispatch_fn(_TOOL_REGISTRY),
        poll_fn=_default_poll,
    )
    result = asyncio.run(runner.run(
        baselines=baselines,
        build_path=args.build_path,
        chrome_bin=args.chrome_bin,
        port=args.port,
        timeout=args.timeout,
    ))

    if args.junit:
        w = JUnitWriter("luna_ci")
        for c in result.cases:
            if c["kind"] == "pass":
                w.add_pass(c["name"])
            elif c["kind"] == "failure":
                w.add_failure(c["name"], c.get("message", ""))
            else:
                w.add_error(c["name"], c.get("message", ""))
        w.write(args.junit)

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
