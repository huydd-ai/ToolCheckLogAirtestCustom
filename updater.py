"""Self-update for the dagster runner.

Pulls the latest dagster/ code from origin on every invocation of
dagster_run.py. Best-effort: any failure (network, missing git, conflict)
logs a warning to stderr and returns - never blocks the run.

Devs opt out either by setting DAGSTER_NO_UPDATE=1 in the environment, or
by creating a marker file `.no-update` in the dagster/ directory. Parent-
only execution: child processes spawned with `--device <serial>` skip,
because only the parent should run `git pull`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_MARKER_FILENAME = ".no-update"
_ENV_VAR = "DAGSTER_NO_UPDATE"


def _is_opted_out(repo_root: Path) -> bool:
    if os.environ.get(_ENV_VAR) == "1":
        return True
    if (repo_root / _MARKER_FILENAME).exists():
        return True
    return False


def _current_branch(repo_root: Path) -> str | None:
    """Return the currently checked-out branch, or None on detached HEAD / error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"[WARN] update: rev-parse failed: {e}", file=sys.stderr)
        return None
    branch = result.stdout.strip()
    if branch == "HEAD" or not branch:
        return None
    return branch


def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
        
    branch = _current_branch(repo_root)
    if not branch:
        print("[WARN] update: detached HEAD or unknown branch, skipping", file=sys.stderr)
        return
        
    # Network/git steps land in later tasks
    return
