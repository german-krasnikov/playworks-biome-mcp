"""Server-side LLM verification via claude CLI subprocess.

Enable: LUNA_VISUAL_LLM=1
Uses `claude -p` for cheap/fast playable ad analysis. Zero API keys needed.
"""
import asyncio
import atexit
import logging
import os
import shutil
import weakref
from typing import Optional

_log = logging.getLogger(__name__)

# WeakSet of active asyncio.subprocess.Process objects.
# Populated in _run_inner; used by _cleanup_subprocesses on SIGTERM/exit.
_active_procs: weakref.WeakSet = weakref.WeakSet()


def _cleanup_subprocesses() -> None:
    """Kill any in-flight subprocesses at process exit. Fail-open."""
    for proc in list(_active_procs):
        try:
            if proc.returncode is None:
                proc.kill()
        except Exception as e:
            _log.debug("cleanup_subprocesses: %s", e)


atexit.register(_cleanup_subprocesses)

CLAUDE_CMD = os.environ.get("LUNA_CLAUDE_CMD", "claude")

SYS_VERIFY = "You verify a Luna playable ad in iframe. Answer PASS or FAIL + 1 short reason. Nothing else."
SYS_UI = ("Playable ad screenshot. List visible UI ONLY: buttons, end-card, install CTA, "
           "tutorial hint, score, timer. Format: 'btn:Play@center, cta:Install@bottom, score:120'. "
           "≤30 words. No prose.")
SYS_STATE = ("Classify playable state. Output ONE token: "
              "loading|tutorial|gameplay|win|fail|endcard|install. Then colon + one fact.")


class SamplingService:
    """Claude CLI calls for server-side Luna playable ad analysis."""

    # Class-level (shared across all instances) — intentional global cap.
    # Default limit=4 via LUNA_VISUAL_CONCURRENCY env var.
    _semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._semaphore is None:
            limit = int(os.environ.get("LUNA_VISUAL_CONCURRENCY", "4"))
            cls._semaphore = asyncio.Semaphore(limit)
        return cls._semaphore

    @property
    def enabled(self) -> bool:
        if os.environ.get("LUNA_VISUAL_LLM") != "1":
            return False
        return shutil.which(CLAUDE_CMD) is not None

    async def _run(self, args: list, timeout: float = 30.0) -> Optional[str]:
        async with self._get_semaphore():
            return await self._run_inner(args, timeout)

    async def _run_inner(self, args: list, timeout: float) -> Optional[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        except Exception:
            return None
        _active_procs.add(proc)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode().strip() or None
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), 2.0)
            except (asyncio.TimeoutError, Exception):
                pass
            return None
        except BaseException as e:
            if proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), 2.0)
                except BaseException:
                    pass
            if isinstance(e, asyncio.CancelledError):
                raise
            return None

    async def verify_visual_state(self, expected: str, png_path: str) -> Optional[str]:
        if not self.enabled or not os.path.isfile(png_path):
            return None
        prompt = f"{SYS_VERIFY}\n\nExpected: {expected}"
        return await self._run(
            [CLAUDE_CMD, "-p", prompt, "--model", "haiku", "--max-turns", "1", png_path],
            timeout=30.0,
        )

    async def describe_image(self, prompt: str, png_path: str) -> Optional[str]:
        if not self.enabled or not os.path.isfile(png_path):
            return None
        return await self._run(
            [CLAUDE_CMD, "-p", prompt, "--model", "haiku", "--max-turns", "1", png_path],
            timeout=30.0,
        )

    async def verify_visual_diff(self, before: str, after: str, what: str) -> Optional[str]:
        if not self.enabled:
            return None
        if not (os.path.isfile(before) and os.path.isfile(after)):
            return None
        prompt = f"Compare these two screenshots. {what}"
        return await self._run(
            [CLAUDE_CMD, "-p", prompt, "--model", "haiku", "--max-turns", "1", before, after],
            timeout=30.0,
        )

    async def describe_image_multi(self, prompt: str, image_paths: list, system: str = "") -> Optional[str]:
        """Pass N images to single Haiku call. Returns text or None if disabled."""
        if not self.enabled:
            return None
        if not image_paths:
            return None
        full = f"{system}\n\n{prompt}" if system else prompt
        cmd = [CLAUDE_CMD, "-p", full, "--model", "haiku", "--max-turns", "1"]
        for p in image_paths:
            cmd.append(p)
        return await self._run(cmd, timeout=60.0)

    async def plan(self, intent: str, system_prompt: str, ctx: str = "") -> Optional[str]:
        """Run Haiku without image input to get a batch DSL plan. Returns None if disabled."""
        if not self.enabled:
            return None
        full_prompt = f"{system_prompt}\n\nINTENT: {intent}"
        if ctx:
            full_prompt = f"{full_prompt}\n\nCONTEXT:\n{ctx}"
        return await self._run(
            [CLAUDE_CMD, "-p", full_prompt, "--model", "haiku", "--max-turns", "1"],
            timeout=30.0,
        )
