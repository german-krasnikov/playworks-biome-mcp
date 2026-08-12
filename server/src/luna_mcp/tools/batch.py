"""Batch command parser and executor."""
from __future__ import annotations

import inspect
import os
import shlex

_TOOL_REGISTRY: dict[str, tuple] = {}
_VALIDATE = os.environ.get("LUNA_MCP_VALIDATE", "1") != "0"
_COERCIBLE = {int, float, bool, str}


def derive_params(fn) -> dict[str, type]:
    """Build a param-type dict from fn's signature, mirroring coerce_args coercible types."""
    import typing
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}
    result = {}
    for name, p in inspect.signature(fn).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = hints.get(name, p.annotation)
        result[name] = ann if ann in _COERCIBLE else str
    return result


def register_batch_tool(name: str, handler, params):
    """Register a tool for batch execution. params=None derives from fn signature."""
    if params is None:
        params = derive_params(handler)
    _TOOL_REGISTRY[name] = (handler, params)


def parse_command(line: str) -> tuple[str, dict]:
    """Parse 'cmd key=value key=value' into (cmd_name, kwargs)."""
    parts = shlex.split(line.strip())
    if not parts:
        raise ValueError("Empty command")
    cmd = parts[0]
    kwargs = {}
    for part in parts[1:]:
        if "=" not in part:
            raise ValueError(f"Invalid arg (no =): {part}")
        key, val = part.split("=", 1)
        kwargs[key] = val
    return cmd, kwargs


def coerce_args(kwargs: dict[str, str], param_types: dict[str, type]) -> dict:
    """Convert string values to expected types."""
    result = {}
    for key, val in kwargs.items():
        t = param_types.get(key)
        if t == int:
            result[key] = int(val)
        elif t == float:
            result[key] = float(val)
        elif t == bool:
            result[key] = val.lower() in ("true", "1", "yes")
        else:
            result[key] = val
    return result


async def _pre_flight(lines: list[tuple[str, dict]], path_cache) -> tuple[int, str] | None:
    """Validate all steps. Returns (step_index, block_msg) on first failure, None if all pass."""
    from luna_mcp.schema_guard import _GUARD
    if _GUARD is None or not _VALIDATE:
        return None
    for i, (cmd, kwargs) in enumerate(lines):
        try:
            block = await _GUARD.validate(cmd, dict(kwargs), path_cache)
            if block:
                return i, block
        except Exception:
            pass
    return None


async def execute_batch(commands_text: str, mode: str = "continue", dry_run: bool = False) -> str:
    """Execute batch commands, return combined results.

    dry_run=True: validate all steps without executing — returns DRY-RUN OK or ABORTED.
    """
    raw_lines = [l.strip() for l in commands_text.strip().split("\n") if l.strip()]

    # Parse all lines first (needed for dry_run pre-flight)
    parsed: list[tuple[str, dict]] = []
    for line in raw_lines:
        try:
            cmd, kwargs = parse_command(line)
            parsed.append((cmd, kwargs))
        except Exception as e:
            if dry_run:
                return f"[BATCH ABORTED at step 0]\nparse error: {e}"
            parsed.append(("?", {}))

    if dry_run:
        failure = await _pre_flight(parsed, None)
        if failure:
            step, block = failure
            return f"[BATCH ABORTED at step {step + 1}]\n{block}"
        return f"[DRY-RUN OK] all {len(parsed)} steps validated"

    results = []
    path_cache = None
    failure = await _pre_flight(parsed, path_cache)
    if failure:
        step, block = failure
        return f"[BATCH ABORTED at step {step + 1}]\n{block}"

    for i, (cmd, kwargs) in enumerate(parsed):
        try:
            if cmd not in _TOOL_REGISTRY:
                raise ValueError(f"Unknown command: {cmd}")
            handler, param_types = _TOOL_REGISTRY[cmd]
            typed_kwargs = coerce_args(kwargs, param_types)
            result = await handler(**typed_kwargs)
            results.append(f"--- {cmd} ---\n{result}")
        except Exception as e:
            error_text = f"--- {cmd} ---\nerror: {e}"
            results.append(error_text)
            if mode == "stop":
                break
    return "\n\n".join(results)
