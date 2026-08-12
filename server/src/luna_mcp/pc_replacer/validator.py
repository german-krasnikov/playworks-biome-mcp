"""Validator: wraps existing visual_baseline_check."""
from __future__ import annotations

from typing import Awaitable, Callable


class Validator:
    def __init__(self, baseline_check_fn: Callable[..., Awaitable[str]]):
        self._check = baseline_check_fn

    async def validate(self, baseline_name: str) -> tuple[bool, str]:
        """Returns (passed, summary)."""
        try:
            result = await self._check(baseline_name)
        except Exception as e:
            return (False, f"error: {e}")
        passed = "PASS" in result
        return (passed, result)
