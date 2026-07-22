# Dagster Runner Self-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auto-`git pull` step at the top of `dagster_run.py:main()` so test machines always run the latest dagster code, with a clean opt-out for dev machines and best-effort (warn-but-continue) failure handling.

**Architecture:** One new self-contained module `dagster/updater.py` exposing `check_and_update(repo_root, is_parallel_child)`. Called as the first action in `dagster_run.py:main()`, before any `pixon` import or argv parsing. All git interaction via `subprocess.run` with explicit timeouts. Helpers are private (`_is_opted_out`, `_current_branch`, `_fetch`, `_commits_behind`, `_pull_ff`). Unit tests fully mock `subprocess.run` — no real git, no real network.

**Tech Stack:** Python 3.10+ stdlib (`subprocess`, `os`, `pathlib`, `sys`). Pytest with `monkeypatch` and `capsys`. No new dependencies.

**Reference spec:** `docs/superpowers/specs/2026-06-12-self-update-design.md`

---

## File Structure

**Create:**
- `dagster/updater.py` — module under test.
- `dagster/test_updater.py` — unit tests, beside the module (mirrors existing convention: `test_reporting.py` beside `reporting.py`, `test_parallel_utils.py` beside `parallel_utils.py`).

**Modify:**
- `dagster/dagster_run.py:31-34` — add three lines at the top of `main()` to call `check_and_update`.
- `dagster/.gitignore` — add `.no-update` so the dev opt-out marker is never committed.
- `dagster/README.md` — add a brief section documenting the opt-out env var and marker file.
- `dagster/CLAUDE.md` — one-line note on the auto-update behavior, so future contributors know the runner self-updates.

**Convention notes:**
- Test files in this repo import without the `dagster.` prefix (e.g. `test_parallel_utils.py` does `from parallel_utils import ...`). Pytest is run with `cwd=dagster/`. New test file follows the same pattern.
- `dagster_run.py` itself uses the `dagster.` prefix for imports (e.g. `from dagster.runner import run_single_test`). The new call follows the same pattern: `from dagster.updater import check_and_update`.

---

## Task 1: Scaffold module + implement opt-out detection

**Goal:** Land the file structure and the simplest skip paths (parallel-child, env var, marker file). Establish the test pattern that the rest of the tasks reuse.

**Files:**
- Create: `dagster/updater.py`
- Create: `dagster/test_updater.py`

- [ ] **Step 1: Write the three failing tests**

Create `dagster/test_updater.py` with:

```python
"""Unit tests for dagster.updater. All git interaction is mocked."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import updater


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    """Build a successful CompletedProcess result for mock fakes."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


def test_check_and_update_skips_when_parallel_child(monkeypatch, repo_root):
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=True)
    assert calls == []


def test_check_and_update_skips_when_env_opt_out(monkeypatch, repo_root):
    monkeypatch.setenv("DAGSTER_NO_UPDATE", "1")
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=False)
    assert calls == []


def test_check_and_update_skips_when_marker_file_present(monkeypatch, repo_root):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    (repo_root / ".no-update").write_text("")
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=False)
    assert calls == []
```

- [ ] **Step 2: Run the new tests, expect collection failure**

Run:
```
cd D:\AutoRebase\dagster
python -m pytest test_updater.py -v
```
Expected: collection error — `ModuleNotFoundError: No module named 'updater'`.

- [ ] **Step 3: Create the module with opt-out support**

Create `dagster/updater.py`:

```python
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


def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
    # Network/git steps land in later tasks; for now stop here so the
    # opt-out tests pass without invoking subprocess.
    return
```

- [ ] **Step 4: Run the three tests, expect PASS**

Run:
```
python -m pytest test_updater.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add dagster/updater.py dagster/test_updater.py
git commit -m "feat(dagster): scaffold updater module with opt-out detection"
```

---

## Task 2: Branch detection + detached-HEAD / missing-git handling

**Goal:** Detect the current branch via `git rev-parse`. Skip with a warning if HEAD is detached, the binary is missing, or rev-parse fails for any other reason.

**Files:**
- Modify: `dagster/updater.py`
- Modify: `dagster/test_updater.py`

- [ ] **Step 1: Add two failing tests**

Append to `dagster/test_updater.py`:

```python
def test_check_and_update_skips_on_detached_head(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _ok(stdout="HEAD\n")  # detached HEAD sentinel

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert len(calls) == 1
    assert calls[0][:3] == ["git", "rev-parse", "--abbrev-ref"]
    assert "detached" in capsys.readouterr().err.lower()


def test_check_and_update_warns_when_git_missing(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "rev-parse failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run the two new tests, expect FAIL**

Run:
```
python -m pytest test_updater.py::test_check_and_update_skips_on_detached_head test_updater.py::test_check_and_update_warns_when_git_missing -v
```
Expected: both FAIL — current `check_and_update` never invokes subprocess and prints nothing.

- [ ] **Step 3: Add `_current_branch` and wire it in**

Edit `dagster/updater.py`. Add this helper above `check_and_update`:

```python
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
```

Replace the body of `check_and_update` with:

```python
def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
    branch = _current_branch(repo_root)
    if branch is None:
        print("[WARN] update: detached HEAD or unable to determine branch, skipping", file=sys.stderr)
        return
    # Fetch / behind-check / pull steps land in later tasks.
    return
```

- [ ] **Step 4: Run the full updater test file, expect PASS**

Run:
```
python -m pytest test_updater.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add dagster/updater.py dagster/test_updater.py
git commit -m "feat(dagster): updater detects current branch, skips on detached HEAD"
```

---

## Task 3: Fetch + behind-check, including warn paths

**Goal:** Implement `git fetch` and the `git rev-list --count HEAD..origin/<branch>` step. Warn-and-return on either failure. No-op when already up to date.

**Files:**
- Modify: `dagster/updater.py`
- Modify: `dagster/test_updater.py`

- [ ] **Step 1: Add three failing tests**

Append to `dagster/test_updater.py`:

```python
def test_check_and_update_warns_on_fetch_timeout(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            raise subprocess.TimeoutExpired(cmd=args, timeout=15)
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "fetch failed" in capsys.readouterr().err


def test_check_and_update_warns_on_fetch_nonzero_exit(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            raise subprocess.CalledProcessError(returncode=128, cmd=args, stderr="auth failed")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "fetch failed" in capsys.readouterr().err


def test_check_and_update_noop_when_already_up_to_date(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="0\n")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    op_names = [c[1] for c in calls]
    assert op_names == ["rev-parse", "fetch", "rev-list"]
    assert "already up to date" in capsys.readouterr().err
```

- [ ] **Step 2: Run the three new tests, expect FAIL**

Run:
```
python -m pytest test_updater.py::test_check_and_update_warns_on_fetch_timeout test_updater.py::test_check_and_update_warns_on_fetch_nonzero_exit test_updater.py::test_check_and_update_noop_when_already_up_to_date -v
```
Expected: all 3 FAIL — current `check_and_update` returns after `_current_branch` and never reaches fetch.

- [ ] **Step 3: Add `_fetch` and `_commits_behind` and wire them in**

Edit `dagster/updater.py`. Add these helpers above `check_and_update`:

```python
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
```

Replace the body of `check_and_update` with:

```python
def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
    branch = _current_branch(repo_root)
    if branch is None:
        print("[WARN] update: detached HEAD or unable to determine branch, skipping", file=sys.stderr)
        return
    if not _fetch(repo_root, branch):
        return
    behind = _commits_behind(repo_root, branch)
    if behind is None:
        return
    if behind == 0:
        print("[INFO] update: already up to date", file=sys.stderr)
        return
    # Fast-forward merge lands in Task 4.
    return
```

- [ ] **Step 4: Run the full updater test file, expect PASS**

Run:
```
python -m pytest test_updater.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```
git add dagster/updater.py dagster/test_updater.py
git commit -m "feat(dagster): updater fetches from origin and detects commits behind"
```

---

## Task 4: Pull (fast-forward) + happy path + pull-failure handling

**Goal:** Implement `git merge --ff-only origin/<branch>` and the success log. Warn-and-return on non-FF or any other merge failure.

**Files:**
- Modify: `dagster/updater.py`
- Modify: `dagster/test_updater.py`

- [ ] **Step 1: Add two failing tests**

Append to `dagster/test_updater.py`:

```python
def test_check_and_update_pulls_when_behind(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="3\n")
        if args[1] == "merge":
            return _ok()
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    op_names = [c[1] for c in calls]
    assert op_names == ["rev-parse", "fetch", "rev-list", "merge"]
    # Verify the merge call shape exactly
    merge_call = calls[-1]
    assert merge_call == ["git", "merge", "--ff-only", "origin/main"]
    assert "pulled 3 commits on main" in capsys.readouterr().err


def test_check_and_update_warns_on_pull_failure(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="2\n")
        if args[1] == "merge":
            raise subprocess.CalledProcessError(returncode=1, cmd=args, stderr="non-fast-forward")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "pull failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run the two new tests, expect FAIL**

Run:
```
python -m pytest test_updater.py::test_check_and_update_pulls_when_behind test_updater.py::test_check_and_update_warns_on_pull_failure -v
```
Expected: both FAIL — current `check_and_update` returns after `_commits_behind` without ever calling `git merge`.

- [ ] **Step 3: Add `_pull_ff` and the success log**

Edit `dagster/updater.py`. Add this helper above `check_and_update`:

```python
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
```

Replace the body of `check_and_update` with:

```python
def check_and_update(repo_root: Path, is_parallel_child: bool) -> None:
    """Pull the latest dagster/ code from origin. Best-effort, never raises."""
    if is_parallel_child:
        return
    if _is_opted_out(repo_root):
        print("[INFO] update: opt-out", file=sys.stderr)
        return
    branch = _current_branch(repo_root)
    if branch is None:
        print("[WARN] update: detached HEAD or unable to determine branch, skipping", file=sys.stderr)
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
```

- [ ] **Step 4: Run the full updater test file, expect PASS**

Run:
```
python -m pytest test_updater.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Run the full repo test suite, expect no regressions**

Run:
```
python -m pytest test_updater.py test_reporting.py test_aggregate_report.py test_parallel_utils.py -v
```
Expected: all tests pass (10 new + the existing count from the report-system tests).

- [ ] **Step 6: Commit**

```
git add dagster/updater.py dagster/test_updater.py
git commit -m "feat(dagster): updater pulls fast-forward from origin when behind"
```

---

## Task 5: Integrate into `dagster_run.py` + manual smoke test

**Goal:** Call `check_and_update` as the first action of `main()`, before any `pixon` import or argv parsing. Verify the end-to-end behavior on the developer's box with three manual scenarios.

**Files:**
- Modify: `dagster/dagster_run.py:31-34` (insert at the top of `main()`)

- [ ] **Step 1: Edit `dagster_run.py:main()`**

The current top of `main()` (`dagster/dagster_run.py:31-34`) reads:

```python
def main():
    # 1. Setup Environment & Capture Hooks
    setup_console_logging(LOG_LEVEL)
    patch_run_step()
```

Replace with:

```python
def main():
    # 1a. Self-update from origin (best-effort, never blocks the run).
    # Parent-only: when --device <serial> is in argv we are a parallel child
    # and the parent already pulled - skip to avoid concurrent `git pull`.
    from dagster.updater import check_and_update
    check_and_update(repo_root=_dagster_dir, is_parallel_child=("--device" in sys.argv))

    # 1b. Setup Environment & Capture Hooks
    setup_console_logging(LOG_LEVEL)
    patch_run_step()
```

Note: the import is deferred inside `main()` rather than placed at the top of the module on purpose. The update may pull a new version of `updater.py` (or sibling modules) before the rest of `main()` runs, so we want the import to happen on the *current* checkout each invocation, not at module-load time. (The first invocation after the update will pick up the new code on the next run, not this one - that is acceptable per the spec.)

- [ ] **Step 2: Manual smoke 1 — happy path (already up to date)**

From `D:\AutoRebase` (host project root, with a connected device or emulator):

```
python dagster/dagster_run.py Test/HeartSystem/tc01_*.air
```

Expected: stderr shows `[INFO] update: already up to date` (or `[INFO] update: pulled N commits on <branch>` if origin had new commits), then the rest of the run proceeds normally.

- [ ] **Step 3: Manual smoke 2 — env var opt-out**

```powershell
$env:DAGSTER_NO_UPDATE = "1"
python dagster/dagster_run.py Test/HeartSystem/tc01_*.air
Remove-Item Env:DAGSTER_NO_UPDATE
```

Expected: stderr shows `[INFO] update: opt-out` and no `git fetch` is attempted. Local edits in `dagster/` are not touched.

- [ ] **Step 4: Manual smoke 3 — fetch failure tolerated**

Temporarily disconnect from the network (turn off Wi-Fi, or block `github.com` in the firewall), then:

```
python dagster/dagster_run.py Test/HeartSystem/tc01_*.air
```

Expected: stderr shows `[WARN] update: fetch failed: ...`. The run still proceeds with the currently checked-out code.

- [ ] **Step 5: Commit**

```
git add dagster/dagster_run.py
git commit -m "feat(dagster): run check_and_update at top of main() to auto-pull on every invocation"
```

---

## Task 6: Documentation + `.gitignore`

**Goal:** Make the opt-out discoverable and prevent the marker file from being accidentally committed.

**Files:**
- Modify: `dagster/.gitignore`
- Modify: `dagster/README.md`
- Modify: `dagster/CLAUDE.md`

- [ ] **Step 1: Check whether `dagster/.gitignore` exists and what it contains**

Run:
```
type dagster\.gitignore
```
Expected: either the existing contents print, or an error indicating the file is missing.

- [ ] **Step 2: Add `.no-update` to `.gitignore`**

If `dagster/.gitignore` exists, append a section:

```
# Self-update opt-out marker (per-machine, never committed)
.no-update
```

If it does not exist, create `dagster/.gitignore` with exactly that content (plus a trailing newline).

- [ ] **Step 3: Document the opt-out in `dagster/README.md`**

Locate the "Run" section of `dagster/README.md` (the section that already describes `python dagster/dagster_run.py ...`). Immediately after the run examples, add a new sub-section:

```markdown
### Self-update

Each invocation of `dagster_run.py` starts with a best-effort `git pull --ff-only` against `origin/<current-branch>`. Test machines stay current automatically; the run continues even if the pull fails (network down, missing git binary, non-fast-forward).

To disable the auto-update on a dev machine, do **either** of:

- Set the environment variable `DAGSTER_NO_UPDATE=1`, **or**
- Create an empty file `dagster/.no-update` (gitignored).

Parallel multi-device runs only pull in the parent process; children invoked with `--device <serial>` skip the update so that N devices do not trigger N concurrent pulls.
```

- [ ] **Step 4: Add a one-liner to `dagster/CLAUDE.md`**

Locate the "Run" section of `dagster/CLAUDE.md`. Immediately above the code fence that shows the `python dagster/dagster_run.py ...` examples, add this paragraph:

```markdown
**Self-update:** every invocation begins with a best-effort `git pull --ff-only` of `dagster/` from `origin/<current-branch>` (see `updater.py`). Opt out on dev boxes with `DAGSTER_NO_UPDATE=1` or by touching `dagster/.no-update`. Failures warn but never block the run.
```

- [ ] **Step 5: Commit**

```
git add dagster/.gitignore dagster/README.md dagster/CLAUDE.md
git commit -m "docs(dagster): document self-update opt-out and gitignore marker file"
```

---

## Verification Summary

| Behavior | How to verify |
|---|---|
| Opt-out via env var | `test_check_and_update_skips_when_env_opt_out` (Task 1) + manual smoke 2 (Task 5). |
| Opt-out via marker file | `test_check_and_update_skips_when_marker_file_present` (Task 1). |
| Parallel children skip | `test_check_and_update_skips_when_parallel_child` (Task 1). |
| Detached HEAD skip | `test_check_and_update_skips_on_detached_head` (Task 2). |
| Missing git binary | `test_check_and_update_warns_when_git_missing` (Task 2). |
| Fetch network failure | `test_check_and_update_warns_on_fetch_timeout`, `test_check_and_update_warns_on_fetch_nonzero_exit` (Task 3) + manual smoke 3 (Task 5). |
| No-op when up to date | `test_check_and_update_noop_when_already_up_to_date` (Task 3) + manual smoke 1 (Task 5). |
| Happy-path pull | `test_check_and_update_pulls_when_behind` (Task 4) + manual smoke 1 (Task 5). |
| Pull failure (non-FF) | `test_check_and_update_warns_on_pull_failure` (Task 4). |
| Integration into dagster_run.py | Manual smoke 1-3 (Task 5). |
| Marker file gitignored | Task 6 Step 2 ensures `.gitignore` is updated; reviewers can verify with `git status` after `touch dagster/.no-update`. |

After all six tasks are committed: full test suite green (`python -m pytest test_updater.py test_reporting.py test_aggregate_report.py test_parallel_utils.py -v`), `dagster_run.py` invocation prints either `[INFO] update: ...` or `[WARN] update: ...` as the very first stderr line of every parent run.
