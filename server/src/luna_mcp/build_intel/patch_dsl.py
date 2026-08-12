"""PatchOp DSL: dataclass + validator + apply."""
from dataclasses import dataclass
from typing import Optional

from .index import JakefileIndex


@dataclass(frozen=True)
class PatchOp:
    id: str
    intent: str
    search: str
    replace: str
    expected_count: int = 1
    anchor_before: Optional[str] = None
    anchor_after: Optional[str] = None
    max_distance: int = 200
    expected_version_sha: Optional[str] = None


def validate(op: PatchOp, file_text: str, index: JakefileIndex) -> tuple:
    if op.expected_version_sha and op.expected_version_sha != index.version_sha:
        return (False, f"version mismatch: expected {op.expected_version_sha} got {index.version_sha}")
    occurrences = file_text.count(op.search)
    if occurrences != op.expected_count:
        return (False, f"search occurs {occurrences} times, expected {op.expected_count}")
    idx_search = file_text.find(op.search) if (op.anchor_before or op.anchor_after) else -1
    if op.anchor_before:
        if op.anchor_before not in file_text:
            return (False, f"anchor_before '{op.anchor_before[:30]}' not found")
        idx_anchor = file_text.rfind(op.anchor_before, 0, idx_search)
        if idx_anchor < 0 or (idx_search - idx_anchor) > op.max_distance:
            return (False, f"anchor_before not within {op.max_distance} chars of search")
    if op.anchor_after:
        idx_after = idx_search + len(op.search)
        idx_anchor = file_text.find(op.anchor_after, idx_after, idx_after + op.max_distance)
        if idx_anchor < 0:
            return (False, f"anchor_after not within {op.max_distance} chars after search")
    return (True, "")


def apply_op(op: PatchOp, file_text: str) -> str:
    return file_text.replace(op.search, op.replace, op.expected_count)
