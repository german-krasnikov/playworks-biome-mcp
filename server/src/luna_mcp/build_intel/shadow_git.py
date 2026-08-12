"""Atomic patch apply/revert via shadow git repo."""
import pathlib
import shutil
import subprocess
from typing import Optional


class ShadowGit:
    def __init__(self, base_dir: pathlib.Path, project_hash: str):
        self._dir = base_dir / project_hash
        self._dir.mkdir(parents=True, exist_ok=True)

    def _run(self, *args, cwd: Optional[pathlib.Path] = None) -> tuple:
        try:
            r = subprocess.run(
                args, cwd=str(cwd) if cwd else str(self._dir),
                capture_output=True, text=True, timeout=30,
            )
            return (r.returncode, r.stdout + r.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (-1, str(e))

    def init_if_needed(self) -> bool:
        if (self._dir / ".git").exists():
            return True
        rc, _ = self._run("git", "init", "-q")
        if rc != 0:
            return False
        self._run("git", "config", "user.email", "playworks-biome@local")
        self._run("git", "config", "user.name", "PlayworksBiome")
        self._run("git", "commit", "--allow-empty", "-q", "-m", "init", "--no-gpg-sign")
        return True

    def stage_file(self, src: pathlib.Path, name: str) -> pathlib.Path:
        target = self._dir / name
        shutil.copy2(str(src), str(target))
        return target

    def commit(self, message: str) -> Optional[str]:
        rc, _ = self._run("git", "add", "-A")
        if rc != 0:
            return None
        rc, _ = self._run("git", "commit", "-q", "-m", message, "--no-gpg-sign")
        if rc != 0:
            return None
        rc, out = self._run("git", "rev-parse", "HEAD")
        if rc != 0:
            return None
        return out.strip()

    def revert_commit(self, sha: str) -> bool:
        rc, _ = self._run("git", "cat-file", "-e", sha)
        if rc != 0:
            return False
        rc, _ = self._run("git", "reset", "--hard", f"{sha}^")
        return rc == 0

    def get_file(self, name: str) -> Optional[pathlib.Path]:
        p = self._dir / name
        return p if p.exists() else None
