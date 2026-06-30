# Graph Report - dagster  (2026-06-30)

## Corpus Check
- 29 files · ~1,613,688 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 622 nodes · 857 edges · 39 communities (33 shown, 6 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 116 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bcc1443e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]

## God Nodes (most connected - your core abstractions)
1. `generate_summary_report()` - 24 edges
2. `render_html()` - 17 edges
3. `regenerate_global_report()` - 17 edges
4. `group_by_date()` - 15 edges
5. `write_log_txt()` - 15 edges
6. `ReportHandler` - 15 edges
7. `ScrcpyRecorder` - 14 edges
8. `scan_runs()` - 13 edges
9. `run_single_test()` - 13 edges
10. `_normalize_and_filter_airtest_log()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Aggregate Report Generator` --semantically_similar_to--> `Report Generator`  [INFERRED] [semantically similar]
  aggregate_report.py → reporting.py
- `Backend Review Fixes Plan` --references--> `Report Generator`  [EXTRACTED]
  docs/superpowers/plans/2026-06-12-backend-review-fixes.md → reporting.py
- `Backend Review Fixes Plan` --references--> `Test Execution Orchestrator`  [EXTRACTED]
  docs/superpowers/plans/2026-06-12-backend-review-fixes.md → runner.py
- `Claude Code Guidance` --semantically_similar_to--> `User Documentation`  [INFERRED] [semantically similar]
  CLAUDE.md → README.md
- `test_parse_simple_stem()` --calls--> `parse_run_folder_name()`  [INFERRED]
  test_aggregate_report.py → aggregate_report.py

## Hyperedges (group relationships)
- **Test Report Pipeline** — step_capture, reporting, aggregate_report, report_server [EXTRACTED 1.00]
- **Test Execution Lifecycle** — updater, dagster_run, runner, step_capture, reporting, log_utils, ScrcpyRecorder [EXTRACTED 1.00]
- **Multi-Device Parallel Execution** — parallel_utils, dagster_run, ProcessBasedParallelism [EXTRACTED 1.00]

## Communities (39 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (69): _append_catalog(), _append_date_group(), build_catalog(), _count_statuses(), _device_summary(), extract_device(), extract_status(), extract_suite() (+61 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (60): _fmt_secs(), generate_html(), generate_summary_report(), _normalize_and_filter_airtest_log(), _parse_airtest_log(), Format seconds as compact human duration: '4.21s', '1m 04s', '1h 02m 03s'., Generate Airtest HTML report from NDJSON log., Parse Airtest's NDJSON log into command rows: one row per logged action.      Ea (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (29): Step Duration Field, Next-Invocation Update Semantic, Parent-Only Git Pull, Process-Based Multi-Device Parallelism, Report Pipeline Architecture, run_step() Monkey-Patch Architecture, Scrcpy Lifecycle Pattern, Scrcpy Screen Recorder (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (42): main(), attach_error_handler(), clear_errors(), ErrorCaptureHandler, get_errors(), Captures ERROR and CRITICAL logs to _errors list., Idempotently attach ErrorCaptureHandler to the target logger., latest_screenshot() (+34 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (44): code:python ("""Unit tests for dagster.updater. All git interaction is mo), code:block10 (python -m pytest test_updater.py -v), code:block11 (git add dagster/updater.py dagster/test_updater.py), code:python (def test_check_and_update_warns_on_fetch_timeout(monkeypatch), code:block13 (python -m pytest test_updater.py::test_check_and_update_warn), code:python (def _fetch(repo_root: Path, branch: str) -> bool:), code:python (def check_and_update(repo_root: Path, is_parallel_child: boo), code:block16 (python -m pytest test_updater.py -v) (+36 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (16): list_devices(), parse_adb_devices(), partition(), Pure helpers for the parallel multi-device runner. No Airtest imports., Split items into n balanced contiguous chunks (sizes differ by <= 1).      Rem, Parse `adb devices` stdout; return serials whose state is exactly 'device'., Enumerate connected ADB devices in the 'device' state.      Prefers the adb bu, test_list_devices_returns_empty_on_failure() (+8 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (6): _ok(), Unit tests for dagster.updater. All git interaction is mocked., Build a successful CompletedProcess result for mock fakes., test_check_and_update_skips_when_env_opt_out(), test_check_and_update_skips_when_marker_file_present(), test_check_and_update_skips_when_parallel_child()

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (27): Backend Review Fixes Implementation Plan, Bug 1 — Dev mode runs invisible to aggregate report, code:python (if mode == "tester":), code:block10 (python -m pytest test_reporting.py::test_generate_html_propa), code:block11 (python -m pytest test_reporting.py test_aggregate_report.py ), code:bash (git add dagster/reporting.py dagster/test_reporting.py), code:python (finally:), code:block14 (python -m pytest -v -k "status" 2>&1 | head -20) (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (15): _compute_etag(), extract_air_path(), _find_newest_folder(), _find_running_job(), _prune_jobs(), Simple HTTP server for the aggregate test report.  Serves static files from RE, Resolve folder_name under REPORT_ROOT, rejecting path traversal.     Returns th, Read AIR_PATH= from first line of log.txt. Returns None if absent or unreadable. (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (5): _install_quiet_excepthook(), Keep a live scrcpy stream for the whole recording, reconnecting on drop., Swallow scrcpy's expected 'Video stream is disconnected' thread crash.      scrc, Record device screen via the scrcpy stream into a single continuous MP4.      Fr, ScrcpyRecorder

### Community 12 - "Community 12"
Cohesion: 0.08
Nodes (25): code:python (# dagster/test_opencv_annotator.py), code:python (from dagster.OpenCVAnnotator import OpenCVAnnotator), code:python (OpenCVAnnotator.reset(test_name=module_name)), code:python (try:), code:python (if recorder:), code:python (finally:), code:bash (git add dagster/runner.py dagster/test_runner_annotation.py), code:python (# dagster/test_reporting_annotation.py) (+17 more)

### Community 13 - "Community 13"
Cohesion: 0.1
Nodes (20): 1. Catalog scan (filesystem, independent of `report_run/`), 2. Catalog ⋈ history join, 3. `POST /run` endpoint, 4. Report regroup: Suite → Day → runs, 5. Catalog UI tab, Architecture, code:block1 (Server-rendered report.html (both tabs built at generation t), code:block2 (suite = Path(air_path).parent.name      # e.g. .../Test/Hear) (+12 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (16): code:python (def _hooked_run_step(name: str, action: Callable[..., Any], ), code:python (try:), code:python (def test_generate_summary_report_called_from_runner_integrat), code:bash (git add runner.py test_reporting.py), code:bash (git add step_capture.py), code:python (def generate_summary_report(out_dir, tc_name, steps, status,), code:python (import html as _html), code:python (status_cls = "pass" if status == "PASS" else "fail") (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (16): Architecture, code:python (class ErrorCaptureHandler(logging.Handler):), code:python (from dagster.error_capture import attach_error_handler), code:python (errors = get_errors()), `dagster/dagster_run.py`, `dagster/reporting.py`, `dagster/runner.py` (`run_single_test`), Data Flow (per test) (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (15): code:javascript (if(r.ok){location.reload();}), code:bash (python -B -c "), code:bash (python -B -c "), code:javascript (if(r.ok){window.location.href='report.html?_='+Date.now();}), code:bash (python -c "), code:bash (rtk pytest test_aggregate_report.py -v), code:python (class ReportHandler(SimpleHTTPRequestHandler):), code:python (class ReportHandler(SimpleHTTPRequestHandler):) (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.14
Nodes (12): 1. `step_capture.py` — Add `duration` field, 2. `reporting.py` — Add `generate_summary_report()`, 3. `runner.py` — Call `generate_summary_report()`, Approach: Custom `report_summary.html`, code:python (overall_status = "FAIL" if error_top or any(s["status"] == "), code:python (try:), Error Handling, Files Changed (+4 more)

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (12): Architecture, code:python (def check_and_update(repo_root: Path, is_parallel_child: boo), code:block2 (dagster_run.py main()), Components, Dagster Runner Self-Update — Design, Data Flow, Decisions, Error Handling (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.15
Nodes (12): Architecture, code:python (class OpenCVAnnotator:), code:block2 (dagster/), Error handling, File changes summary, Frame annotations, Integration points, New file: `dagster/OpenCVAnnotator.py` (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.24
Nodes (6): DeviceCaps, DeviceManager, Manages the pool of Android devices for test sharding., Runs adb devices and returns a list of connected serials., Checks if a device is booted, and probes its capabilities., Discovers and returns a list of healthy devices.

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (10): code:powershell (# Run a single .air test in tester mode (default)), code:powershell (# Start the local server), Contents, Dagster — Airtest Runner + Scrcpy Recorder, Execution Modes, Global Dashboard, Limitations, Requirements (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.2
Nodes (8): Architecture (non-obvious — spans runner + pixon), code:block1 (# single test), code:block2 (report_run/<air_stem>_<YYYYMMDD_HHMMSS>/), Conventions, Host dependency (critical — this repo is not self-running), Output, Run, What this is

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (8): code:python (def test_render_html_has_tab_bar():), code:python ('<div class="tabs">',), code:python (html.append('</div>')  # end tab-report), code:python (def _append_catalog(html: list[str], catalog: list[tuple[str), code:css (.tabs { display: flex; gap: 8px; margin-bottom: 20px; }), code:javascript (function showTab(name) {), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 6: Render the Test Catalog tab (HTML + CSS + JS)

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (7): code:python (def test_extract_suite_from_air_path(tmp_path):), code:python (_AIR_PATH_RE = re.compile(r"^AIR_PATH=(.+)$", re.MULTILINE)), code:python (def extract_suite(log_path: Path) -> str:), code:python (@dataclass(frozen=True)), code:python (suite = extract_suite(log_path)), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 1: `suite` field on `RunEntry`, populated in `scan_runs`

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (6): code:python (def test_run_rejects_path_outside_test_root(tmp_path):), code:python (PROJECT_ROOT = _project_root), code:python (if self.path == "/run":), code:python (def _handle_run(self) -> None:), code:bash (git add report_server.py test_rerun.py), Task 9: `POST /run` endpoint with path confinement

### Community 28 - "Community 28"
Cohesion: 0.47
Nodes (3): checkEmpty(), deleteAllRuns(), deleteRun()

### Community 29 - "Community 29"
Cohesion: 0.4
Nodes (5): code:python (def test_render_html_groups_by_suite():), code:python (def _append_date_group(html: list[str], date_str: str, rows:), code:python (def render_html(suite_groups: list[tuple[str, list[tuple[str), code:bash (git add aggregate_report.py test_aggregate_report.py test_re), Task 5: Refactor `render_html` to suite → day grouping

### Community 30 - "Community 30"
Cohesion: 0.4
Nodes (5): code:python (def test_find_running_job_keys_on_suite_and_stem(tmp_path):), code:python (def _find_running_job(suite: str, stem: str) -> dict | None:), code:python (suite = Path(air_path).parent.name or "unknown"), code:bash (git add report_server.py test_rerun.py), Task 8: Shared `(suite, stem)` concurrency guard in `report_server.py`

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (3): Background facts (read once), Self-Review, Test Catalog + Suite-Grouped Report Implementation Plan

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (4): code:python (def test_scan_catalog_lists_air_by_suite(tmp_path):), code:python (def scan_catalog(test_root: Path) -> dict[str, list[str]]:), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 3: `scan_catalog` — filesystem scan of `../Test/`

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (3): code:python (def test_build_catalog_joins_last_run(tmp_path):), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 4: `build_catalog` — join catalog with run history

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (4): code:python (def test_regenerate_renders_suite_groups_and_catalog(tmp_pat), code:python (def regenerate_global_report(report_root: Path, test_root: P), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 7: Wire catalog into `regenerate_global_report`

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (3): code:python (def _entry_s(stem, dt_str, status, suite):), code:bash (git add aggregate_report.py test_aggregate_report.py), Task 2: `group_by_suite_then_date`

## Knowledge Gaps
- **272 isolated node(s):** `Aggregate per-run report folders into a single global report.html.`, `Escape a value for use as a single-quoted JS string literal inside a     double`, `Read DEVICE= from log.txt head. Returns 'unknown' if absent (e.g. old runs).`, `Suite = parent dir name of AIR_PATH in log.txt head. 'unknown' if absent.`, `Map suite folder -> sorted .air stems under test_root/<suite>/. All test cases,` (+267 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `regenerate_global_report()` connect `Community 0` to `Community 8`, `Community 3`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 3` to `Community 0`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `run_single_test()` connect `Community 3` to `Community 9`, `Community 1`, `Community 23`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `generate_summary_report()` (e.g. with `run_single_test()` and `test_generate_summary_report_writes_file()`) actually correct?**
  _`generate_summary_report()` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `render_html()` (e.g. with `test_render_html_contains_doctype_and_title()` and `test_render_html_empty_state()`) actually correct?**
  _`render_html()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `regenerate_global_report()` (e.g. with `main()` and `.do_POST()`) actually correct?**
  _`regenerate_global_report()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `group_by_date()` (e.g. with `test_group_by_date_dates_sorted_descending()` and `test_group_by_date_within_group_sorted_newest_first()`) actually correct?**
  _`group_by_date()` has 11 INFERRED edges - model-reasoned connections that need verification._