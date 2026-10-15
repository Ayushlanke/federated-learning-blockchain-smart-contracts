"""Run manifests: everything needed to reproduce a result.

Implements the reproducibility contract in EVALUATION_PLAN.md section 6. A results
file without a manifest is an anecdote; with one it is an experiment.

Captured: experiment id, git commit and dirty flag, exact command line, all
parameters, RNG seeds, resolved package versions, Python build, OS/CPU, core count,
and wall-clock duration. The **dirty flag** matters more than it looks -- a result
produced from uncommitted code cannot be reproduced from the repository, and silently
recording only the commit SHA would misrepresent it as reproducible.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["Manifest", "capture_environment"]

_TRACKED_PACKAGES = (
    "numpy",
    "torch",
    "scipy",
    "scikit-learn",
    "pandas",
    "cryptography",
    "matplotlib",
    "pytest",
)


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _package_versions() -> Dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    resolved: Dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            resolved[name] = version(name)
        except PackageNotFoundError:
            resolved[name] = "not installed"
    return resolved


def capture_environment() -> Dict[str, Any]:
    """Snapshot of everything about this machine that could change a timing result."""
    import os

    dirty = _git("status", "--porcelain")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(dirty) if dirty is not None else None,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "machine": platform.machine(),
        "cpu_count_logical": os.cpu_count(),
        "packages": _package_versions(),
    }


@dataclass
class Manifest:
    """Provenance record written next to every results file."""

    experiment_id: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    seeds: Dict[str, int] = field(default_factory=dict)
    command: List[str] = field(default_factory=lambda: list(sys.argv))
    environment: Dict[str, Any] = field(default_factory=capture_environment)
    started_unix: float = field(default_factory=time.time)
    duration_s: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        """Record something a reader must know to interpret the numbers."""
        self.notes.append(text)

    def finish(self) -> None:
        self.duration_s = time.time() - self.started_unix

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)

    def save(self, directory: Path | str) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "manifest.json"
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    def reproduction_command(self) -> str:
        """The exact command that regenerates this result."""
        return " ".join(self.command)

    def warnings(self) -> List[str]:
        """Conditions that weaken reproducibility. Empty is good."""
        issues: List[str] = []
        env = self.environment
        if env.get("git_dirty"):
            issues.append(
                "Working tree was DIRTY: this result cannot be reproduced from the "
                "committed repository state."
            )
        if env.get("git_commit") is None:
            issues.append("No git commit recorded (not a repository?).")
        missing = [k for k, v in env.get("packages", {}).items() if v == "not installed"]
        if missing:
            issues.append(f"Packages not installed: {', '.join(missing)}")
        return issues
