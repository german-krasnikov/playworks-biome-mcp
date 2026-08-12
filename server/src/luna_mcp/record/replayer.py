"""Replay session against live Chrome.
Implemented divergence signals:
- result_hash mismatch (with SOFT-OK on first-50-chars summary match)
TODO: scene_fp, console errors delta (not yet wired).
"""
import json
import pathlib
from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass
class ReplayReport:
    ok_steps: int = 0
    diverged_at: int = -1
    divergence_reason: str = ""
    total: int = 0
    summary: list = field(default_factory=list)


class Replayer:
    def __init__(self, dispatch_fn: Callable[..., Awaitable[str]]):
        self._dispatch = dispatch_fn

    async def replay(self, path: pathlib.Path, dry_run: bool = False) -> ReplayReport:
        from .fingerprint import hash_result
        from .redact import redact_result
        report = ReplayReport()
        if not path.exists():
            report.divergence_reason = f"file not found: {path}"
            return report
        with path.open() as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            report.divergence_reason = "bad header"
            return report
        try:
            json.loads(lines[0])  # validate header
        except Exception:
            report.divergence_reason = "bad header"
            return report
        report.total = len(lines) - 1
        for i, raw in enumerate(lines[1:], start=1):
            try:
                step = json.loads(raw)
            except Exception:
                report.diverged_at = i
                report.divergence_reason = "bad json"
                return report
            if dry_run:
                report.summary.append(f"[{i} DRY] {step['tool']} {step.get('args')}")
                report.ok_steps += 1
                continue
            try:
                result = await self._dispatch(step["tool"], **step.get("args", {}))
            except Exception as e:
                report.diverged_at = i
                report.divergence_reason = f"call failed: {type(e).__name__}: {e}"
                return report
            new_hash = hash_result(redact_result(step["tool"], result))
            if new_hash != step["hash"]:
                new_summary = redact_result(step["tool"], result)[:50]
                old_summary = step.get("summary", "")[:50]
                if new_summary == old_summary:
                    report.summary.append(f"[{i} SOFT-OK] {step['tool']}")
                    report.ok_steps += 1
                    continue
                report.diverged_at = i
                report.divergence_reason = f"hash mismatch: was={step['hash']} now={new_hash}"
                report.summary.append(f"[{i} DIV] {step['tool']}: {new_summary}")
                return report
            report.summary.append(f"[{i} OK] {step['tool']}")
            report.ok_steps += 1
        return report

    async def diff(self, path_a: pathlib.Path, path_b: pathlib.Path) -> str:
        with path_a.open() as fa, path_b.open() as fb:
            steps_a = [json.loads(l) for l in fa.readlines()[1:] if l.strip()]
            steps_b = [json.loads(l) for l in fb.readlines()[1:] if l.strip()]
        out = []
        for i, (sa, sb) in enumerate(zip(steps_a, steps_b)):
            if sa["tool"] != sb["tool"]:
                out.append(f"[{i+1} TOOL-DIV] {sa['tool']} vs {sb['tool']}")
            elif sa["hash"] != sb["hash"]:
                out.append(
                    f"[{i+1} HASH-DIV] {sa['tool']}: "
                    f"{sa.get('summary','')[:40]} → {sb.get('summary','')[:40]}"
                )
            else:
                out.append(f"[{i+1} OK] {sa['tool']}")
        if len(steps_a) != len(steps_b):
            out.append(f"[LEN-DIV] {len(steps_a)} vs {len(steps_b)}")
        return "\n".join(out[:100])
