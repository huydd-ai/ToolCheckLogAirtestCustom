# Dagster Runner Self-Update — Design

**Date:** 2026-06-12
**Status:** Approved, ready for plan

## Goal

Auto-pull the latest `dagster/` runner code on every `dagster_run.py` invocation so test machines never run stale code. Dev machines opt out so local edits aren't clobbered. Best-effort: network or git failures warn but never block the run.

## Decisions

| Axis | Choice |
|---|---|
| Update scope | `dagster/` repo only (own remote: `https://github.com/huydd-ai/ToolCheckLogAirtestCustom.git`). `pixon/` and `Test/` are not touched. |
| Delivery mechanism | `git pull` (fast-forward only) from origin. |
| Trigger | Auto on every `dagster_run.py` invocation, as the first action in `main()`. |
| Dev opt-out | Two equivalent signals (either is sufficient): env var `DAGSTER_NO_UPDATE=1`, or marker file `dagster/.no-update`. |
| Failure mode | Warn and continue with current checkout — never abort the run. |
| Branch tracked | The currently checked-out local branch's same-name upstream on `origin`. (Detached HEAD = skip with warning.) |
| Concurrency safety | Only the parent process runs the update. Child processes (`--device <serial>` in argv) skip — protects against N devices triggering N concurrent `git pull` collisions. |

## Architecture

One new module `dagster/updater.py` exposing one public function:

```python
def check_and_update(repo_root: Path, is_parallel_child: bool) -> None: ...
```

Called as the first statement of `dagster_run.py:main()`, before any `pixon` import, before argv parsing, before device init. Side-effecting, returns `None`, never raises (all exceptions caught at the boundary and logged as `[WARN] update: ...`).

**Self-contained.** Imports only `subprocess`, `os`, `pathlib`, `sys`. No dependency on `pixon`, no dependency on other dagster modules. Two reasons:

1. The update pulls *new* versions of `runner.py`, `reporting.py`, `aggregate_report.py`, etc. The function that triggers the pull cannot have already imported them — Python caches modules at first import.
2. If `updater.py` itself ships a bug, the impact is contained to this one file's import path.

**Parent-only execution.** When `_run_parallel` (or any future orchestrator) re-invokes `dagster_run.py` with `--device <serial>`, the child skips the update. This is encoded as `is_parallel_child = "--device" in sys.argv`. The parent process pulls once, then children inherit the updated checkout.

## Components

| File | Role |
|---|---|
| `dagster/updater.py` (new) | Module. Public: `check_and_update()`. Private helpers: `_is_opted_out`, `_current_branch`, `_fetch`, `_commits_behind`, `_pull_ff`. |
| `dagster/test_updater.py` (new) | Unit tests. All git interaction mocked via `monkeypatch.setattr(updater.subprocess, "run", ...)`. No real git invocations. |
| `dagster/dagster_run.py` (modify) | Add three lines at the top of `main()` to import + call `check_and_update`. |
| `dagster/.gitignore` (modify) | Add `.no-update` so the opt-out marker file is never committed. |
| `dagster/README.md` (modify) | Document the opt-out env var and marker file. |
| `dagster/CLAUDE.md` (modify) | One-line note on the auto-update behavior for future contributors. |

## Data Flow

```
dagster_run.py main()
  └─> updater.check_and_update(repo_root=dagster_dir, is_parallel_child)
        ├─ if is_parallel_child:                            → return (silent)
        ├─ if _is_opted_out(repo_root):                     → log "[INFO] update: opt-out", return
        ├─ branch = _current_branch(repo_root)
        │    └─ if branch in (None, "HEAD"):                → log "[WARN] update: detached HEAD, skipping", return
        ├─ _fetch(repo_root, branch)
        │    └─ on TimeoutExpired/CalledProcessError:       → log "[WARN] update: fetch failed: <reason>", return
        ├─ behind = _commits_behind(repo_root, branch)
        │    └─ on error:                                   → log "[WARN] update: rev-list failed", return
        │    └─ if behind == 0:                             → log "[INFO] update: already up to date", return
        ├─ _pull_ff(repo_root, branch)
        │    └─ on error (e.g., non-FF, conflict):          → log "[WARN] update: pull failed: <reason>", return
        └─ log "[INFO] update: pulled <N> commits on <branch>"
```

All subprocess calls use `cwd=repo_root`, `capture_output=True`, `text=True`, and an explicit `timeout=`.

**Timeouts (seconds):**

| Call | Timeout |
|---|---|
| `git rev-parse --abbrev-ref HEAD` | 5 |
| `git fetch origin <branch>` | 15 |
| `git rev-list --count HEAD..origin/<branch>` | 5 |
| `git merge --ff-only origin/<branch>` | 10 |

## Error Handling

Every subprocess call is wrapped in `try/except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError)`. On any failure, a single `[WARN] update: <op>: <reason>` line is printed to stderr and the function returns. The run continues with whatever code is currently checked out.

`FileNotFoundError` covers the case where `git` itself isn't on PATH — relevant for trimmed test boxes. We don't try to bundle git; we just log and continue.

Non-fast-forward (the local branch has diverged from origin) also lands here — `_pull_ff` fails with `CalledProcessError`. We never force-push or hard-reset the user's tree.

## Testing Strategy

**Unit tests in `test_updater.py`** — fully mocked subprocess, no real git, no real network. Use `monkeypatch.setattr(updater.subprocess, "run", fake)` where `fake` is a callable that returns a `subprocess.CompletedProcess` (or raises) per the test's scenario.

Test cases:

1. `test_check_and_update_skips_when_parallel_child` — call with `is_parallel_child=True`, assert `subprocess.run` was never invoked.
2. `test_check_and_update_skips_when_env_opt_out` — set `DAGSTER_NO_UPDATE=1` via `monkeypatch.setenv`, assert no fetch attempted.
3. `test_check_and_update_skips_when_marker_file_present` — create `.no-update` in `tmp_path`, assert no fetch attempted.
4. `test_check_and_update_skips_on_detached_head` — mock `rev-parse` to return `HEAD`, assert no fetch attempted, warn logged.
5. `test_check_and_update_warns_on_fetch_timeout` — mock fetch to raise `TimeoutExpired`, assert warn logged + function returns.
6. `test_check_and_update_warns_on_fetch_nonzero_exit` — mock fetch to raise `CalledProcessError`, assert warn logged + returns.
7. `test_check_and_update_warns_when_git_missing` — mock `subprocess.run` to raise `FileNotFoundError`, assert warn logged + returns.
8. `test_check_and_update_noop_when_already_up_to_date` — mock fetch OK, rev-list returns `0`, assert no `merge` call made.
9. `test_check_and_update_pulls_when_behind` — mock fetch OK, rev-list returns `3`, assert `merge --ff-only` called with correct args + success log emitted.
10. `test_check_and_update_warns_on_pull_failure` — mock merge to raise `CalledProcessError` (non-FF), assert warn logged + function returns without re-raising.

**Manual smoke** (documented but not automated):

- On a clean prod-style checkout: run `python dagster/dagster_run.py Test/HeartSystem/tc01_*.air`, push a no-op commit to origin, run again, observe `[INFO] update: pulled 1 commits on main`.
- On a dev-style checkout: set `DAGSTER_NO_UPDATE=1`, edit `runner.py`, run, observe `[INFO] update: opt-out` and the edit is preserved.
- Network-off: disconnect, run, observe `[WARN] update: fetch failed: ...` and run still proceeds.

## Out of Scope (Anti-scope)

- Updating `pixon/`, `Test/`, or anything outside the `dagster/` repo. The host project owns those.
- Version pinning, signed tags, rollback UX. Plain `git pull` on the tracked branch is enough — rollback = `git reset --hard <sha>` by hand on the rare occasion it's needed.
- Self-update of `git` itself or any system dependency.
- Server-push notifications, websockets, polling daemons. The model is "pull on invocation" — no background process.
- Cross-platform install scripts. The dagster runner is already Windows-only (`scrcpy-win64/` is vendored). Same constraint applies here.

## Open Questions

None — all axes decided during brainstorming.
