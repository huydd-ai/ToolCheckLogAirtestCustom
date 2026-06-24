# Test Catalog + Suite-Grouped Report — Design

**Date:** 2026-06-24
**Status:** Approved, ready for plan
**Author:** huydd

## Problem

Today the report UI (`report_server.py` + `aggregate_report.py`) only surfaces test
cases that have **already been run** — each run leaves a `<stem>_<date>_<time>/` folder
under `report_run/`, and the global `report.html` lists those folders grouped **by date
only**. You cannot:

1. Browse the full set of test cases that *exist* in `../Test/<Suite>/*.air` (never-run
   ones are invisible).
2. Start a fresh test case from the UI (only **rerun** of an existing folder works).
3. Read the report organized by suite folder, then by day.

## Goal

- A **Test Catalog** tab in the existing report UI that lists every `.air` test case in
  `../Test/`, grouped by suite folder, including never-run ones, each with a ▶ Run button.
- Starting a test from the catalog **monitors its run live** via the existing log stream.
- The global report **groups by suite folder → day → runs**, replacing the date-only view.

## Non-goals (YAGNI)

- **Live device-screen mirror.** scrcpy already produces an MP4 linked in each per-run
  report → post-run screen review exists. Live MJPEG/WebRTC streaming is out of scope.
- **Auth.** The server already binds `0.0.0.0` unauthenticated by design (single-user
  local tool). `/run` is confined to `../Test/` instead — see §3.
- **Device picker.** `dagster_run.py` already auto-enumerates ADB devices; the Run button
  defers to that default (auto single/parallel).

## Architecture

Pure extension of the two existing modules. No new dependencies. Reuses the dark theme,
the `_jobs` job machinery, and the live-log stream.

```
Browser (report.html)
  ├── Report tab      ── GET /api/runs        → scan_runs()            (suite-grouped render)
  └── Catalog tab     ── GET /api/catalog      → scan_catalog() ⋈ scan_runs()
                         POST /run {air_path}  → guard → spawn dagster_run.py → _jobs
                         GET  /rerun-logs/<id>  ┐
                         GET  /rerun-status/<id>├─ EXISTING, unchanged, reused by /run
                         POST /rerun-terminate/<id> ┘
```

### The unifying move: a `suite` field

The suite name is **not** stored in the run folder name (`<stem>_<date>_<time>` carries
only the test-case stem). It exists only in the `AIR_PATH=` line written to every run's
`log.txt` (verified: `reporting.write_log_txt` is always called with `air_path=` from
`runner.py:164`). `AIR_PATH` holds the **resolved absolute path**, so:

```
suite = Path(air_path).parent.name      # e.g. .../Test/HeartSystem/tc01_...air → "HeartSystem"
```

Add `suite: str = "unknown"` to `RunEntry`. Populate it in `scan_runs` by reading
`AIR_PATH` (reuse the same read `extract_air_path` already does) and taking the parent dir
name. Runs whose `log.txt` lacks `AIR_PATH` (old runs) fall into an explicit `"unknown"`
suite bucket — they must **not** silently vanish.

This single field powers **both** report grouping (§4) and catalog↔history matching (§2)
on `(suite, stem)` — avoiding collisions when two suites contain a same-named `.air`.

## Components

### 1. Catalog scan (filesystem, independent of `report_run/`)

New helper (in `aggregate_report.py` or a small new module):

```
scan_catalog(test_root: Path) -> dict[str, list[str]]   # {suite: [stem, ...]}
```

- Glob `test_root / "*/*.air"` → files only, so `__pycache__` dirs are excluded naturally.
- Suite = `air_file.parent.name`; stem = `air_file.stem`.
- Sorted suites, sorted stems. Returns **all** test cases, run or not.

`test_root` resolves to `../Test` relative to the project root (same host-dependency
pattern `dagster_run.py` already uses).

### 2. Catalog ⋈ history join

`/api/catalog` returns, per suite, per test case:

```json
{ "suite": "HeartSystem", "stem": "tc01_check_ui_ux_heart",
  "air_path": "Test/HeartSystem/tc01_check_ui_ux_heart.air",
  "run_count": 3, "last_status": "PASS", "last_run_href": "tc01_..._20260624_101500/report.html" }
```

Join `scan_catalog()` against `scan_runs()` on `(suite, stem)`. Never-run tests →
`run_count: 0, last_status: null, last_run_href: null`. Join done **server-side** (single
source of truth); the browser just renders.

### 3. `POST /run` endpoint

Takes a client-supplied `air_path` (relative, from the catalog). **Guard before `Popen`:**

```python
TEST_ROOT = (PROJECT_ROOT / "Test").resolve()      # resolved ONCE at startup
p = (PROJECT_ROOT / air_path).resolve()
if not (p.is_file() and p.suffix == ".air" and TEST_ROOT in p.parents):
    return 400  # reject — confines launch to ../Test/, blocks arbitrary-file exec
```

Both sides resolved so symlink / `..` tricks cannot escape `Test/`. On pass, reuse the
**exact** existing spawn flow from `_handle_rerun`: `Popen([python, "-u", dagster_run.py,
air_path])`, register in `_jobs`, return `{job_id}`. Live log / status / terminate via the
existing `/rerun-logs`, `/rerun-status`, `/rerun-terminate` endpoints — unchanged.

**Concurrency guard (shared with rerun).** `/rerun` already refuses a second launch of the
same `stem` while one is running (returns 409). `/run` must hit the **same** guard, keyed
on `(suite, stem)` — otherwise a catalog ▶ and a report rerun could launch the same test
twice and collide on Airtest's process-global `G.DEVICE`. Refactor the guard so both paths
share it.

### 4. Report regroup: Suite → Day → runs

Replace `group_by_date` with `group_by_suite_then_date`:

```
list[ (suite, list[ (date_str, list[RunEntry]) ]) ]
```

Render: suite folder = top-level collapsible `<details>`; day = nested collapsible
(today open by default, matching current behavior); run rows reuse the **existing** row
markup (status badge, device, links, delete, rerun). `delete` / `delete-date` / `rerun`
endpoints unchanged. Suites sorted alphabetically; days newest-first; `"unknown"` suite
sorts last.

### 5. Catalog UI tab

Add a tab toggle to `report.html` (`Report` | `Test Catalog`), same page, same theme.
Catalog view: per suite a collapsible section listing its test cases; each row shows the
status badge from the join (or "never run") + a ▶ Run button. Run button → `POST /run` →
on `job_id`, open the **existing** live-log panel/poller (same component reruns use).

## Structural cleanups (do while touching, not prerequisites)

- **Extract job manager.** `report_server.py` already mixes static-serve + delete +
  job-manager + rerun; catalog + `/run` push it past comfortable. While editing, move
  `_jobs`, `_jobs_lock`, `_handle_rerun*`, the shared concurrency guard, and `/run` into a
  `jobs.py`. *ponytail: only because you're already in the file — not a standalone refactor.*
- **Maybe split render.** `aggregate_report.py` is ~26KB with inline HTML/CSS/JS. If the
  catalog tab adds significant markup, split a `render.py` (HTML strings) from the
  scan/group/data logic. Judgment call at write time.
- **Cap `_jobs`.** The dict is never pruned and each run drops a `<job_id>.log` in
  `report_run/`; cheap catalog launches make this leak faster. Add a simple cap: on new
  job, drop done jobs beyond the most-recent N (and unlink their stale `.log`).
  *ponytail: bounded dict, not a background reaper.*

## Error handling

- `/run` bad/escaping path → 400 with JSON error; UI shows inline message.
- `/run` while same `(suite, stem)` already running → 409 "already running" (reuse existing).
- `dagster_run.py` not found → 500 (existing behavior).
- `scan_catalog` when `../Test` missing → return `{}`; catalog tab shows "no test root found"
  (consistent with the host-dependency model where a standalone clone has no `../Test`).
- Run with `AIR_PATH` missing in produced `log.txt` → suite `"unknown"` bucket (no crash).

## Testing

- `test_aggregate_report.py`: extend with suite-grouping cases — including a run whose
  `log.txt` lacks `AIR_PATH` landing in `"unknown"`, and two suites sharing a same-named
  stem not colliding.
- New: `scan_catalog` lists never-run `.air`, excludes `__pycache__`, groups by suite.
- New: `/run` guard rejects paths outside `../Test/`, non-`.air`, and non-existent files;
  accepts a valid in-tree `.air`.
- New: `(suite, stem)` concurrency guard blocks the second concurrent launch.

## Files touched

| File | Change |
|------|--------|
| `aggregate_report.py` | `suite` field on `RunEntry`; populate in `scan_runs`; `scan_catalog`; `group_by_suite_then_date`; suite-grouped render |
| `report_server.py` | `POST /run` + path guard; `GET /api/catalog`; catalog tab HTML/JS; shared concurrency guard; (extract job manager → `jobs.py`) |
| `jobs.py` (new, optional) | `_jobs`, lock, spawn/guard/terminate moved out of `report_server.py` |
| `test_aggregate_report.py` | suite-grouping + unknown-bucket + collision tests |
| new test file(s) | `scan_catalog`, `/run` guard, concurrency guard |
