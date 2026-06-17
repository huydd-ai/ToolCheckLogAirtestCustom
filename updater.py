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


def _fetch(repo_root: Path, branch: str) -> bool:
    """Return True on successful fetch; False otherwise (warning already logged)."""
    try:
        subprocess.run(
            ["git", "fetch", "origin", branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"[WARN] update: fetch failed: {e}", file=sys.stderr)
        return False


def _commits_behind(repo_root: Path, branch: str) -> int | None:
    """Return commits HEAD is behind origin/<branch>, or None on error."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"[WARN] update: rev-list failed: {e}", file=sys.stderr)
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        print(f"[WARN] update: rev-list returned non-integer: {result.stdout!r}", file=sys.stderr)
        return None


def _pull_ff(repo_root: Path, branch: str) -> bool:
    """Return True on successful fast-forward merge; False otherwise (warning already logged)."""
    try:
        subprocess.run(
            ["git", "merge", "--ff-only", f"origin/{branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"[WARN] update: pull failed: {e}", file=sys.stderr)
        return False


def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
    branch = _current_branch(repo_root)
    if branch is None:
        print("[WARN] update: detached HEAD or unknown branch, skipping", file=sys.stderr)
        return
    if not _fetch(repo_root, branch):
        return
    behind = _commits_behind(repo_root, branch)
    if behind is None:
        return
    if behind == 0:
        print("[INFO] update: already up to date", file=sys.stderr)
        return
    if _pull_ff(repo_root, branch):
        print(f"[INFO] update: pulled {behind} commits on {branch}", file=sys.stderr)
    return
