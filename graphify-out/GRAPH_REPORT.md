# Graph Report - dagster  (2026-07-03)

## Corpus Check
- 45 files · ~3,433,024 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1704 nodes · 3619 edges · 100 communities (82 shown, 18 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 192 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e931f0cf`
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
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]

## God Nodes (most connected - your core abstractions)
1. `js()` - 71 edges
2. `an()` - 61 edges
3. `ns()` - 55 edges
4. `n()` - 38 edges
5. `no` - 32 edges
6. `s()` - 29 edges
7. `va` - 28 edges
8. `o()` - 27 edges
9. `updateElements()` - 25 edges
10. `run_single_test()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `patch_run_step()`  [INFERRED]
  dagster_run.py → capture/step_capture.py
- `main()` --calls--> `patch_run_step()`  [INFERRED]
  dagster_run.py → step_capture.py
- `run_single_test()` --calls--> `clear_errors()`  [INFERRED]
  runner.py → capture/error_capture.py
- `run_single_test()` --calls--> `get_errors()`  [INFERRED]
  runner.py → capture/error_capture.py
- `run_single_test()` --calls--> `clear_errors()`  [INFERRED]
  runner.py → error_capture.py

## Hyperedges (group relationships)
- **Test Report Pipeline** — step_capture, reporting, aggregate_report, report_server [EXTRACTED 1.00]
- **Test Execution Lifecycle** — updater, dagster_run, runner, step_capture, reporting, log_utils, ScrcpyRecorder [EXTRACTED 1.00]
- **Multi-Device Parallel Execution** — parallel_utils, dagster_run, ProcessBasedParallelism [EXTRACTED 1.00]

## Communities (100 total, 18 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (68): _append_catalog(), _append_date_group(), build_catalog(), _count_statuses(), _device_summary(), extract_device(), extract_status(), extract_suite() (+60 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (60): _fmt_secs(), generate_html(), generate_summary_report(), _normalize_and_filter_airtest_log(), _parse_airtest_log(), Format seconds as compact human duration: '4.21s', '1m 04s', '1h 02m 03s'., Generate Airtest HTML report from NDJSON log., Parse Airtest's NDJSON log into command rows: one row per logged action.      Ea (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (51): Step Duration Field, Next-Invocation Update Semantic, Parent-Only Git Pull, Process-Based Multi-Device Parallelism, Report Pipeline Architecture, run_step() Monkey-Patch Architecture, Scrcpy Lifecycle Pattern, Scrcpy Screen Recorder (+43 more)

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (16): clear_steps(), _emit_step_log(), get_current(), get_steps(), _hooked_run_step(), _latest_screenshot(), patch_run_step(), Find the most recently modified .jpg/.png in ST.LOG_DIR. (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (44): code:python ("""Unit tests for dagster.updater. All git interaction is mo), code:block10 (python -m pytest test_updater.py -v), code:block11 (git add dagster/updater.py dagster/test_updater.py), code:python (def test_check_and_update_warns_on_fetch_timeout(monkeypatch), code:block13 (python -m pytest test_updater.py::test_check_and_update_warn), code:python (def _fetch(repo_root: Path, branch: str) -> bool:), code:python (def check_and_update(repo_root: Path, is_parallel_child: boo), code:block16 (python -m pytest test_updater.py -v) (+36 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (22): buildLookupTable(), ei(), En, Fo(), _generate(), getDecimalForValue(), _getTimestampsForTable(), ia() (+14 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (38): addBox(), afterEvent(), be(), beforeDatasetDraw(), beforeDatasetsDraw(), beforeLayout(), beforeUpdate(), c() (+30 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (27): Backend Review Fixes Implementation Plan, Bug 1 — Dev mode runs invisible to aggregate report, code:python (if mode == "tester":), code:block10 (python -m pytest test_reporting.py::test_generate_html_propa), code:block11 (python -m pytest test_reporting.py test_aggregate_report.py ), code:bash (git add dagster/reporting.py dagster/test_reporting.py), code:python (finally:), code:block14 (python -m pytest -v -k "status" 2>&1 | head -20) (+19 more)

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
Nodes (10): Architecture (non-obvious — spans runner + pixon), code:block1 (dagster/), code:block2 (# single test), code:block3 (report_run/<air_stem>_<YYYYMMDD_HHMMSS>/), Conventions, Host dependency (critical — this repo is not self-running), Layout, Output (+2 more)

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

### Community 36 - "Community 36"
Cohesion: 0.12
Nodes (18): _any_job_running(), _compute_etag(), extract_air_path(), _find_newest_folder(), _find_running_job(), _prune_jobs(), Simple HTTP server for the aggregate test report.  Serves static files from RE, Evict oldest finished jobs above _JOBS_MAX, closing their log handle and     un (+10 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (5): d(), ie, js(), Ue(), w()

### Community 40 - "Community 40"
Cohesion: 0.07
Nodes (25): Be(), Bt(), cr(), d(), Dn(), et(), F(), fe() (+17 more)

### Community 41 - "Community 41"
Cohesion: 0.08
Nodes (15): at(), Bi(), bt, gt(), jt(), kt(), mt(), qt() (+7 more)

### Community 42 - "Community 42"
Cohesion: 0.05
Nodes (15): As(), bn, ce(), de, dt(), he(), ns(), oe (+7 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (17): afterDraw(), bs, da(), f(), fa(), ga(), ha, ki() (+9 more)

### Community 44 - "Community 44"
Cohesion: 0.4
Nodes (5): build_catalog(), Join scan_catalog() with run history on (suite, stem). Each test gets its     n, Map suite folder -> sorted .air stems under test_root/<suite>/., Map suite folder -> sorted .air stems under test_root/<suite>/., scan_catalog()

### Community 45 - "Community 45"
Cohesion: 0.16
Nodes (29): _(), An(), bi(), Cn(), deleteProperty(), dt(), ge(), get() (+21 more)

### Community 47 - "Community 47"
Cohesion: 0.16
Nodes (11): afterUpdate(), ba(), ea(), ft(), ne(), oi(), Si(), ti() (+3 more)

### Community 48 - "Community 48"
Cohesion: 0.13
Nodes (9): a(), determineDataLimits(), getValueForPixel(), ko, r(), un(), vi(), xo (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.13
Nodes (15): ao(), getCenterPoint(), gi(), ho(), Hs, inRange(), inXRange(), inYRange() (+7 more)

### Community 50 - "Community 50"
Cohesion: 0.15
Nodes (8): co(), Do(), eo(), gn, l(), po(), s(), so()

### Community 52 - "Community 52"
Cohesion: 0.21
Nodes (9): buildTicks(), fn, go(), ii(), parse(), parseArrayData(), parseObjectData(), parsePrimitiveData() (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.16
Nodes (19): $e(), ei(), fi(), I(), Ie(), ir(), jn(), mr() (+11 more)

### Community 54 - "Community 54"
Cohesion: 0.14
Nodes (19): beforeDraw(), dataset(), et(), getRange(), h(), hi(), i, index() (+11 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (17): Architecture, code:block1 (report_run/ folders ──scan(1 head read)──> report_data.scan_), Component 1 — `report_data.py` (new, shared data layer), Component 2 — JSON API (extend `report_server.py`), Component 3 — SPA (new `static/` dir, served by `report_server.py`), Component 4 — Triage features, Component 5 — Backward compatibility, Current state (baseline) (+9 more)

### Community 57 - "Community 57"
Cohesion: 0.21
Nodes (6): ct(), fs(), ge(), ms(), ws, ys()

### Community 58 - "Community 58"
Cohesion: 0.15
Nodes (8): _(), ai(), it(), j(), pt(), q(), to(), wi()

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (15): Architecture, code:python (LDCONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"), code:block2 (Single Run / Rerun:), Component 1 — `ldplayer_ctl.py` (new, `dagster/`, beside `device_manager.py`), Component 2 — two new POST routes in `report_server.py`, Component 3 — `app.js` client sequencing, Data flow, Decisions (locked) (+7 more)

### Community 61 - "Community 61"
Cohesion: 0.17
Nodes (5): _install_quiet_excepthook(), Keep a live scrcpy stream for the whole recording, reconnecting on drop., Swallow scrcpy's expected 'Video stream is disconnected' thread crash.      scrc, Record device screen via the scrcpy stream into a single continuous MP4.      Fr, ScrcpyRecorder

### Community 62 - "Community 62"
Cohesion: 0.23
Nodes (12): deleteDate(), deleteRun(), fetchCatalog(), fetchData(), fetchMetrics(), init(), pollJob(), rerunTest() (+4 more)

### Community 63 - "Community 63"
Cohesion: 0.22
Nodes (3): cs, os(), pi()

### Community 64 - "Community 64"
Cohesion: 0.19
Nodes (8): latest_screenshot(), Find the most recently modified .jpg/.png in ST.LOG_DIR., Attach a stdout StreamHandler to Airtest's loggers so steps print to CLI., setup_console_logging(), get_paths(), main(), main(), regenerate_global_report()

### Community 65 - "Community 65"
Cohesion: 0.25
Nodes (6): attach_error_handler(), clear_errors(), ErrorCaptureHandler, get_errors(), Captures ERROR and CRITICAL logs to _errors list., Idempotently attach ErrorCaptureHandler to the target logger.

### Community 66 - "Community 66"
Cohesion: 0.14
Nodes (10): attach_error_handler(), clear_errors(), ErrorCaptureHandler, get_errors(), Captures ERROR and CRITICAL logs to _errors list., Idempotently attach ErrorCaptureHandler to the target logger., latest_screenshot(), Find the most recently modified .jpg/.png in ST.LOG_DIR. (+2 more)

### Community 67 - "Community 67"
Cohesion: 0.2
Nodes (12): compute_metrics(), extract_error_from_airtest_log(), parse_run_folder_name(), Data layer for the global test report., Compute aggregate metrics: totals, trend, and flaky tests., Compute aggregate metrics: totals, trend, and flaky tests., Read tail of airtest.log to find the last traceback line., RunEntry (+4 more)

### Community 68 - "Community 68"
Cohesion: 0.27
Nodes (11): _append_catalog(), _append_date_group(), _count_statuses(), _device_summary(), group_by_date(), group_by_suite_then_date(), _js_arg(), Aggregate per-run report folders into a single global report.html. (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.16
Nodes (15): a(), ae(), Bn(), C(), Fn(), G(), Gn(), Je() (+7 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (15): ci(), di(), Dr(), Ee(), en(), fr(), Ii(), pr() (+7 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (3): addElements(), afterDatasetsUpdate(), mn()

### Community 72 - "Community 72"
Cohesion: 0.24
Nodes (9): aa(), Ae(), b(), g(), m(), o(), ta(), v() (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.22
Nodes (9): _emit_step_log(), _hooked_run_step(), Emit an Airtest NDJSON 'function' entry so LogToHtml can show the step in report, Emit an Airtest NDJSON 'function' entry so LogToHtml can show the step in report, Take an Airtest snapshot tied to the step name so HTML binds an image to the ste, Take an Airtest snapshot tied to the step name so HTML binds an image to the ste, Intercept run_step calls to capture step name, action, status, screenshot, and e, Intercept run_step calls to capture step name, action, status, screenshot, and e (+1 more)

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (3): dn(), fe(), sn

### Community 75 - "Community 75"
Cohesion: 0.16
Nodes (12): clear_steps(), get_annotator(), get_current(), get_steps(), init_annotator(), patch_run_step(), Return in-flight step name, or last-ran step name if between steps., Return in-flight step name, or last-ran step name if between steps. (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.22
Nodes (12): check_and_update(), _commits_behind(), _current_branch(), _fetch(), _is_opted_out(), _pull_ff(), Self-update for the dagster runner.  Pulls the latest dagster/ code from origin, Pull the latest dagster/ code from origin. Best-effort, never raises. (+4 more)

### Community 77 - "Community 77"
Cohesion: 0.17
Nodes (11): launch(), quit(), Launch/close the LDPlayer emulator for dashboard-triggered test runs.  Single in, Start the LDPlayer instance. Raises FileNotFoundError if ldconsole is missing., Close the LDPlayer instance. Best-effort: logs failures, never raises., Poll for a booted, ADB-healthy device; on first sighting, sleep STABILIZE then r, wait_ready(), No device ever appears -> returns False once virtual clock passes timeout. (+3 more)

### Community 78 - "Community 78"
Cohesion: 0.32
Nodes (7): _fmt_secs(), generate_summary_report(), _parse_airtest_log(), Format seconds as compact human duration: '4.21s', '1m 04s', '1h 02m 03s'., Parse Airtest's NDJSON log into command rows: one row per logged action.      Ea, Write structured log.txt from captured steps., write_log_txt()

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (12): Ce(), Jt(), kn(), Mn(), ownKeys(), q(), rr(), _t() (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.09
Nodes (21): ca(), _calculateBarIndexPixels(), _calculateBarValuePixels(), getBasePixel(), getLabelAndValue(), getLabelForValue(), getPixelForTick(), getPixelForValue() (+13 more)

### Community 82 - "Community 82"
Cohesion: 0.32
Nodes (7): delete_report_folder(), delete_reports_by_pattern(), delete_reports_older_than(), Report cleanup utilities for dagster. Handles deletion of report folders and the, Delete entire report folder and all contents.      Args:         report_path: Pa, Delete report folders matching a pattern.      Args:         report_root: Base r, Delete report folders older than specified days.      Args:         report_root:

### Community 83 - "Community 83"
Cohesion: 0.24
Nodes (6): DeviceCaps, DeviceManager, Manages the pool of Android devices for test sharding., Runs adb devices and returns a list of connected serials., Checks if a device is booted, and probes its capabilities., Discovers and returns a list of healthy devices.

### Community 92 - "Community 92"
Cohesion: 0.38
Nodes (4): _FakeProc, A job marked running whose process already exited must be reaped, not counted —, test_any_job_running_reaps_exited_job_and_returns_false(), test_any_job_running_true_when_running_job_present()

### Community 93 - "Community 93"
Cohesion: 0.33
Nodes (7): br(), ct(), le(), Ln(), Me(), Vn(), Vt()

### Community 95 - "Community 95"
Cohesion: 0.15
Nodes (5): gs(), ks(), p(), Us(), Xs()

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (5): es(), generateLabels(), ls, qi, ts()

### Community 97 - "Community 97"
Cohesion: 0.5
Nodes (4): Er(), he(), Hn(), zn()

## Knowledge Gaps
- **352 isolated node(s):** `Report cleanup utilities for dagster. Handles deletion of report folders and the`, `Delete entire report folder and all contents.      Args:         report_path: Pa`, `Delete report folders matching a pattern.      Args:         report_root: Base r`, `Delete report folders older than specified days.      Args:         report_root:`, `Simple HTTP server for the aggregate test report.  Serves static files from RE` (+347 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 64` to `Community 0`, `Community 65`, `Community 66`, `Community 3`, `Community 75`, `Community 76`, `Community 82`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Why does `n()` connect `Community 80` to `Community 64`, `Community 5`, `Community 6`, `Community 72`, `Community 42`, `Community 43`, `Community 46`, `Community 47`, `Community 48`, `Community 49`, `Community 50`, `Community 52`, `Community 57`, `Community 95`, `Community 63`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `regenerate_global_report()` connect `Community 0` to `Community 64`, `Community 8`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **What connects `Report cleanup utilities for dagster. Handles deletion of report folders and the`, `Delete entire report folder and all contents.      Args:         report_path: Pa`, `Delete report folders matching a pattern.      Args:         report_root: Base r` to the rest of the system?**
  _352 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._