# Dashboard Redesign — Design Spec

**Date:** 2026-06-30
**Status:** Approved, pending implementation plan

## Goal

Replace the static server-rendered global report dashboard with a JSON-API-backed
single-page app that adds: aggregate metrics + trends, visual polish, faster failure
triage, and live updates while tests run.

## Decisions (locked)

| Dimension | Choice |
|-----------|--------|
| Architecture | JSON API (extend `report_server.py`) + SPA frontend |
| Frontend stack | Zero-build: CDN micro-framework (Alpine.js) + Chart.js, single `index.html` |
| Live updates | Polling `/api/runs` with existing ETag (304 = skip re-render) |
| Theme | Reuse `report_theme.THEME_CSS` dark palette |
| Build step | None — preserves Python-only repo + git-pull self-update model |

## Current state (baseline)

- `report_run/<stem>_<YYYYMMDD_HHMMSS>/` per run: `log.txt` (Status, `DEVICE=`, `AIR_PATH=`),
  `report.html`, `*.jpg`, `recording_*.mp4`, `airtest.log`.
- `aggregate_report.py` — scans folders → `RunEntry(stem, when, status, device, suite)`,
  groups by date / suite+date, emits a static global `report.html` string with embedded
  CSS/JS. Already has: text search, status filter pills, device summary, suite catalog.
- `report_server.py` — `ThreadingHTTPServer` over `REPORT_ROOT`; POST actions
  (delete, delete-date, rerun, rerun-terminate, run, run-all); computes ETags.

What's missing: aggregate stats, pass-rate %, trend charts, flakiness, inline error
snippets, live refresh.

## Architecture

### Component 1 — `report_data.py` (new, shared data layer)

Extract scan/parse out of `aggregate_report.py` so both the server API and the static
generator consume one source of truth.

- `RunEntry` — already has `folder` + `report_href` (in `aggregate_report.py`). Add only
  `duration: float | None` and `error_summary: str | None` (last FAIL behaviour, parsed
  from `log.txt`; fall back to last traceback line in `airtest.log`).
- `scan_runs(report_root) -> list[RunEntry]` — moved from `aggregate_report.py`.
  **Single-head-read:** today `extract_status` + `extract_device` + `extract_suite` open
  `log.txt` 3× per folder; adding `error_summary` would make 4×. Under polling this is
  wasteful I/O. Refactor to read the head once and parse all fields from that one buffer.
- `compute_metrics(runs) -> Metrics`:
  - totals: count, pass / fail / skip
  - `pass_rate` (%) overall
  - `by_suite`, `by_device` breakdowns (counts + pass-rate)
  - `trend`: list of `(date, total, pass_rate)` ordered ascending — pass-rate over time
  - `flaky`: tests whose status flips across the most recent N runs of the same stem
    (N configurable, default 10). A test is flaky if it has ≥1 PASS and ≥1 FAIL in window.

**Dependencies:** stdlib + existing regexes from `aggregate_report.py`. No device, no Airtest.
**Testable headless:** unit tests build fixture folders / `RunEntry` lists and assert metrics.

### Component 2 — JSON API (extend `report_server.py`)

New GET endpoints (return `application/json`):

- `GET /api/runs` — serialized `RunEntry` list; sets `ETag` header.
  **ETag must fold in folder mtimes, not just names.** Current `_compute_etag` hashes the
  sorted folder-name list only; a running test's folder name never changes, so a
  name-only ETag returns `304` and the SPA never sees in-progress status flips. Extend the
  ETag input to include each folder's `mtime` (and `/api/jobs` state hash) so live changes
  bust the cache. Returns `304 Not Modified` when `If-None-Match` matches.
- `GET /api/metrics` — serialized `compute_metrics` output.
- `GET /api/catalog` — suites/tests via existing `scan_catalog` (move to `report_data.py`).
- `GET /api/jobs` — **new, required for live updates.** Running-test state lives in the
  in-memory `_jobs` dict in `report_server.py`, *separate from folders* — `scan_runs` cannot
  see it. Expose `_jobs` as JSON: `[{job_id, suite, stem, status, exit_code, started}]`
  (under `_jobs_lock`). The SPA merges `/api/jobs` (in-flight) with `/api/runs` (completed
  folders) to show running tests and reflect status as they finish.

Existing POST actions (`/delete/...`, `/delete-date/...`, rerun, run, terminate) **already
return JSON** (e.g. `/delete/` → `{deleted, logs_cleared}`). Audit each for a consistent
shape the SPA can consume — do **not** rewrite ones that already work.

### Component 3 — SPA (new `static/` dir, served by `report_server.py`)

- `static/index.html` — shell; loads Alpine.js + Chart.js from CDN, `app.js`, `styles.css`.
- `static/styles.css` — imports/reuses `THEME_CSS` palette; card-based layout, responsive grid.
- `static/app.js` — single Alpine component:
  - On load + every ~3s: `fetch('/api/runs', {headers: {'If-None-Match': lastEtag}})`;
    on 304 do nothing, on 200 store data + etag. Also fetch `/api/jobs` each tick (cheap,
    in-memory) and merge running jobs into the run list. Periodically refresh `/api/metrics`.
  - Sections:
    1. **Metrics bar** — cards: total runs, pass-rate % (large), fail count, flaky count.
    2. **Trend chart** — Chart.js: pass-rate line + runs/day bar over `metrics.trend`.
    3. **Filters** — status pills, device dropdown, suite dropdown, text search; all
       client-side over fetched `runs` (instant, no server round-trip).
    4. **Run list** — date-grouped collapsible; per run: status badge, name → opens
       `report.html`, device tag, time, duration, **inline error snippet**, action buttons
       (rerun / terminate / logs / delete) → POST to existing endpoints.
    5. **Catalog** — suites with run-all / run-test buttons.
    6. **Live indicator** — "updating…" pulse during poll; reflect running tests.

### Component 4 — Triage features

- `error_summary` surfaced inline in each failed run row (no drill-in needed for the gist).
- "Failed only" toggle (a filter pill).
- Run name / "open report" deep-links straight to that run's `report.html`.

### Component 5 — Backward compatibility

`aggregate_report.py` static `report.html` generator stays as a `file://` fallback for
offline viewing. The SPA is **additive** — the static generator is refactored to call
`report_data.py` but otherwise keeps working. (ponytail: don't delete working code.)

## Data flow

```
report_run/ folders ──scan(1 head read)──> report_data.scan_runs() ──> RunEntry[]
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                  compute_metrics()   /api/runs      aggregate_report.py
                          │       (ETag=names+mtime)  (static fallback)
                          ▼               │
                     /api/metrics         │
                                          │
   _jobs dict (in-memory) ──> /api/jobs   │
                                  │       │
                                  └───────┴──> SPA (Alpine) ──poll──> merge+render
                                                     │
                                                POST actions ──> report_server handlers
```

## Error handling

- API endpoints wrap scan in try/except → `500 {error}` JSON; SPA shows a non-blocking
  banner, keeps last-good data.
- Malformed / partial run folders (missing `log.txt`) → status `UNKNOWN`, never crash scan
  (current behaviour preserved).
- Poll failure (server down) → SPA shows "disconnected", retries next interval.

## Testing

- `report_data.py`: unit tests for `compute_metrics` (pass-rate, trend ordering, flaky
  detection) and `error_summary` extraction, using fixture `RunEntry` lists / temp folders.
  Headless — no device, no Airtest.
- API: spin `report_server` against a temp `REPORT_ROOT`, assert `/api/runs`, `/api/metrics`,
  `/api/catalog` JSON shape + ETag 304 behaviour.
- SPA: manual smoke (no JS test framework added — YAGNI).

## Phasing (→ implementation plan)

1. `report_data.py` refactor + **single-head-read** for scan + `compute_metrics`
   (trend, flaky) + `error_summary` + unit tests.
2. JSON API endpoints (`/api/runs`, `/api/metrics`, `/api/catalog`, `/api/jobs`) +
   **ETag = folder names + mtimes** + 304 + tests; audit POST-action JSON shapes.
3. SPA shell: run list + filters at parity with current dashboard.
4. Metrics bar + trend charts.
5. Live polling + running-test reflection (merge `/api/jobs` + `/api/runs`).
6. Triage: inline error snippets, failed-only toggle, deep links.

## Out of scope (YAGNI)

- No node/Vite build, no React.
- No SSE (polling chosen).
- No DB / persistence layer — folders remain source of truth, scanned live.
- No auth (local tool, unchanged from today).
