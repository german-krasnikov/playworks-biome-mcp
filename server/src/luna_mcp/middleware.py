"""Middleware: wrap tool functions with SchemaGuard pre-flight validation."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def wrap_with_guard(name: str, fn, params: dict, guard, path_cache_holder) -> tuple:
    """Return (wrapped_fn, params) — wrapped fn does pre-flight before calling fn."""

    async def wrapped(**kw):
        if kw.pop("_no_validate", False):
            return await fn(**kw)
        try:
            pc = path_cache_holder.get() if path_cache_holder else None
            block = await guard.validate(name, kw, pc)
            if block:
                return block
        except Exception:
            logger.debug("wrap_with_guard: guard raised (fail-open)", exc_info=True)
        return await fn(**kw)

    return wrapped, params
