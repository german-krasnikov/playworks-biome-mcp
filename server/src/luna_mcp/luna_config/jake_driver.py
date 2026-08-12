"""Headless Jake build driver.

DRY-RUN by default: returns the command + validation dict.
Only executes a real subprocess when execute=True is explicitly passed.
"""
from __future__ import annotations

import pathlib
import subprocess
from typing import Any


class JakeDriver:
    def __init__(self, project_path: str = "."):
        self.project_path = pathlib.Path(project_path).expanduser().resolve()

    def _validate(self) -> tuple[bool, str]:
        if not self.project_path.exists():
            return False, f"project_path not found: {self.project_path}"
        return True, "ok"

    def _cmd(self) -> str:
        return "./jake build"

    def build(self, dry_run: bool = True, execute: bool = False) -> dict[str, Any]:
        valid, reason = self._validate()
        cmd = self._cmd()

        if dry_run or not execute:
            return {
                "dry_run": True,
                "command": cmd,
                "project_path": str(self.project_path),
                "valid": valid,
                "error": reason if not valid else None,
                "executed": False,
            }

        # Real execution — only reached when execute=True and dry_run=False
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "dry_run": False,
                "command": cmd,
                "executed": True,
                "returncode": proc.returncode,
                "stdout": proc.stdout[:2000],
                "stderr": proc.stderr[:500],
            }
        except subprocess.TimeoutExpired:
            return {"dry_run": False, "executed": True, "error": "timeout after 300s"}
        except Exception as e:
            return {"dry_run": False, "executed": True, "error": str(e)}
