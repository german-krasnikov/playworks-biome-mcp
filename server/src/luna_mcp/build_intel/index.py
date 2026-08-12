"""Extract anchors, task names, and version SHA from a Jakefile.js."""
import hashlib
import pathlib
import re
from dataclasses import dataclass

_TASK_RE = re.compile(r"task\s*\(\s*['\"]([^'\"]+)['\"]")
_STR_RE = re.compile(r"['\"]([^'\"]{12,200})['\"]")
_ANCHOR_MIN_LEN = 12
_ANCHOR_MAX_COUNT = 200
_VERSION_LINE = 6


@dataclass(frozen=True)
class JakefileIndex:
    path: str
    size: int
    task_names: list[str]
    anchors: list[str]
    version_sha: str
    line_count: int

    def to_summary(self) -> str:
        return (
            f"path={self.path}\n"
            f"size={self.size}B lines={self.line_count}\n"
            f"version_sha={self.version_sha}\n"
            f"tasks={','.join(self.task_names[:25])}\n"
            f"anchors_count={len(self.anchors)}"
        )


def build_index(path: pathlib.Path) -> JakefileIndex:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    line_count = len(lines)
    target = lines[_VERSION_LINE - 1] if line_count >= _VERSION_LINE else (lines[0] if lines else "")
    version_sha = hashlib.sha256(target.encode()).hexdigest()[:16]
    task_names = sorted(set(_TASK_RE.findall(text)))
    seen: set = set()
    anchors = []
    for m in _STR_RE.finditer(text):
        s = m.group(1)
        if s in seen:
            continue
        seen.add(s)
        anchors.append(s)
        if len(anchors) >= _ANCHOR_MAX_COUNT:
            break
    return JakefileIndex(
        path=str(path),
        size=path.stat().st_size,
        task_names=task_names,
        anchors=anchors,
        version_sha=version_sha,
        line_count=line_count,
    )
