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
Server-rendered report.html (both tabs built at generation time)
  ├── Report tab   ← scan_runs()                  (suite → day → runs)
  └── Catalog tab  ← scan_catalog() ⋈ scan_runs()  (suite → test cases + last status)
        Run button ── POST /run {air_path}  → guard → spawn dagster_run.py → _jobs
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

New helper in `aggregate_report.py`:

```
scan_catalog(test_root: Path) -> dict[str, list[str]]   # {suite: [stem, ...]}
```

- Glob `test_root / "*/*.air"` → files only, so `__pycache__` dirs are excluded naturally.
- Suite = `air_file.parent.name`; stem = `air_file.stem`.
- Sorted suites, sorted stems. Returns **all** test cases, run or not.

`test_root` resolves to `../Test` relative to the project root (same host-dependency
pattern `dagster_run.py` already uses).

### 2. Catalog ⋈ history join

The catalog tab is **server-rendered HTML** (same pattern as the existing date report — no
JSON API, no client-side join). When building `report.html`, join `scan_catalog()` against
`scan_runs()` on `(suite, stem)` to compute, per test case: `last_status` (or "never run")
and `last_run_href` (link to its newest run's report, or none). Emit the catalog markup
directly. Never-run tests render with a "never run" badge and no link.

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
Catalog view (server-rendered): per suite a collapsible section listing its test cases;
each row shows the status badge from the join (or "never run") + a ▶ Run button. Run
button → `POST /run` → on `job_id`, open the **existing** live-log panel/poller (same
component reruns use).

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
| `aggregate_report.py` | `suite` field on `RunEntry`; populate in `scan_runs`; `scan_catalog`; `group_by_suite_then_date`; suite-grouped render; server-rendered catalog tab + history join |
| `report_server.py` | `POST /run` + path guard; shared `(suite,stem)` concurrency guard |
| `test_aggregate_report.py` | suite-grouping + unknown-bucket + collision tests |
| new test file(s) | `scan_catalog`, `/run` guard, concurrency guard |
