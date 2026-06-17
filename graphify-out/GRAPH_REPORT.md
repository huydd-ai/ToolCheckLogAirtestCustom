# Graph Report - D:\AutoRebase\dagster  (2026-06-16)

## Corpus Check
- Large corpus: 12908 files · ~7,112,612 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 224 nodes · 414 edges · 12 communities (9 shown, 3 thin omitted)
- Extraction: 74% EXTRACTED · 26% INFERRED · 0% AMBIGUOUS · INFERRED: 107 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Aggregate Report & Run Parsing|Aggregate Report & Run Parsing]]
- [[_COMMUNITY_Summary Report & Log Writing|Summary Report & Log Writing]]
- [[_COMMUNITY_Architecture & Design Decisions|Architecture & Design Decisions]]
- [[_COMMUNITY_Test Runner Core|Test Runner Core]]
- [[_COMMUNITY_HTML Report Generation|HTML Report Generation]]
- [[_COMMUNITY_Parallel Device Utilities|Parallel Device Utilities]]
- [[_COMMUNITY_Updater Tests|Updater Tests]]
- [[_COMMUNITY_Self-Update Mechanism|Self-Update Mechanism]]
- [[_COMMUNITY_Report HTTP Server|Report HTTP Server]]
- [[_COMMUNITY_Scrcpy Screen Recording|Scrcpy Screen Recording]]
- [[_COMMUNITY_Documentation|Documentation]]
- [[_COMMUNITY_Vendor Assets|Vendor Assets]]

## God Nodes (most connected - your core abstractions)
1. `generate_summary_report()` - 22 edges
2. `group_by_date()` - 14 edges
3. `render_html()` - 14 edges
4. `write_log_txt()` - 14 edges
5. `regenerate_global_report()` - 12 edges
6. `_normalize_and_filter_airtest_log()` - 12 edges
7. `_entry()` - 12 edges
8. `_read_log()` - 12 edges
9. `scan_runs()` - 11 edges
10. `Report Generator` - 10 edges

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

## Communities (12 total, 3 thin omitted)

### Community 0 - "Aggregate Report & Run Parsing"
Cohesion: 0.09
Nodes (52): extract_status(), group_by_date(), parse_run_folder_name(), Aggregate per-run report folders into a single global report.html., Parse a run folder name `<stem>_YYYYMMDD_HHMMSS` -> (stem, datetime).      Retur, Write `style.css` and `script.js` next to `report.html`., Scan `report_root` for test runs and (re)write `report_root/report.html`.      A, Return PASS/FAIL/SKIP from a run's `log.txt`, or UNKNOWN if missing.      Reads (+44 more)

### Community 1 - "Summary Report & Log Writing"
Cohesion: 0.12
Nodes (37): generate_summary_report(), Write structured log.txt from captured steps., write_log_txt(), _make_step(), End-to-end smoke: function callable with the same args runner.py passes., _read_log(), test_generate_summary_report_banner_shows_fail(), test_generate_summary_report_banner_shows_pass() (+29 more)

### Community 2 - "Architecture & Design Decisions"
Cohesion: 0.11
Nodes (29): Step Duration Field, Next-Invocation Update Semantic, Parent-Only Git Pull, Process-Based Multi-Device Parallelism, Report Pipeline Architecture, run_step() Monkey-Patch Architecture, Scrcpy Lifecycle Pattern, Scrcpy Screen Recorder (+21 more)

### Community 3 - "Test Runner Core"
Cohesion: 0.13
Nodes (16): main(), Attach a stdout StreamHandler to Airtest's loggers so steps print to CLI., setup_console_logging(), Run a single Airtest module, capture steps, video, and generate report. Returns, run_single_test(), clear_steps(), _emit_step_log(), get_steps() (+8 more)

### Community 4 - "HTML Report Generation"
Cohesion: 0.23
Nodes (18): generate_html(), _normalize_and_filter_airtest_log(), Generate Airtest HTML report from NDJSON log., Promote NDJSON entry depths and optionally filter noisy logs for dev mode., _make_entry(), generate_html should raise when LogToHtml import fails — caller handles it., _read_ndjson(), test_generate_html_propagates_exception_on_missing_airtest() (+10 more)

### Community 5 - "Parallel Device Utilities"
Cohesion: 0.17
Nodes (16): list_devices(), parse_adb_devices(), partition(), Pure helpers for the parallel multi-device runner. No Airtest imports., Split items into n balanced contiguous chunks (sizes differ by <= 1).      Rem, Parse `adb devices` stdout; return serials whose state is exactly 'device'., Enumerate connected ADB devices in the 'device' state.      Prefers the adb bu, test_list_devices_returns_empty_on_failure() (+8 more)

### Community 6 - "Updater Tests"
Cohesion: 0.16
Nodes (6): _ok(), Unit tests for dagster.updater. All git interaction is mocked., Build a successful CompletedProcess result for mock fakes., test_check_and_update_skips_when_env_opt_out(), test_check_and_update_skips_when_marker_file_present(), test_check_and_update_skips_when_parallel_child()

### Community 7 - "Self-Update Mechanism"
Cohesion: 0.22
Nodes (12): check_and_update(), _commits_behind(), _current_branch(), _fetch(), _is_opted_out(), _pull_ff(), Self-update for the dagster runner.  Pulls the latest dagster/ code from origin, Pull the latest dagster/ code from origin. Best-effort, never raises. (+4 more)

### Community 8 - "Report HTTP Server"
Cohesion: 0.25
Nodes (3): Simple HTTP server for the aggregate test report.  Serves static files from REPO, ReportHandler, SimpleHTTPRequestHandler

## Knowledge Gaps
- **39 isolated node(s):** `Aggregate per-run report folders into a single global report.html.`, `Parse a run folder name `<stem>_YYYYMMDD_HHMMSS` -> (stem, datetime).      Retur`, `Return PASS/FAIL/SKIP from a run's `log.txt`, or UNKNOWN if missing.      Reads`, `Find run folders under `report_root` that have a finished `log.txt`.      In-pro`, `Group entries by ISO date string (YYYY-MM-DD).      Outer list ordered by date D` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Aggregate Report Generator` connect `Architecture & Design Decisions` to `Aggregate Report & Run Parsing`?**
  _High betweenness centrality (0.328) - this node is a cross-community bridge._
- **Why does `Report Generator` connect `Architecture & Design Decisions` to `Summary Report & Log Writing`?**
  _High betweenness centrality (0.297) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `generate_summary_report()` (e.g. with `run_single_test()` and `test_generate_summary_report_writes_file()`) actually correct?**
  _`generate_summary_report()` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `group_by_date()` (e.g. with `test_group_by_date_dates_sorted_descending()` and `test_group_by_date_within_group_sorted_newest_first()`) actually correct?**
  _`group_by_date()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `render_html()` (e.g. with `test_render_html_contains_doctype_and_title()` and `test_render_html_empty_state()`) actually correct?**
  _`render_html()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `write_log_txt()` (e.g. with `run_single_test()` and `test_write_log_txt_pass_when_all_steps_pass()`) actually correct?**
  _`write_log_txt()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `regenerate_global_report()` (e.g. with `main()` and `test_regenerate_writes_report_html()`) actually correct?**
  _`regenerate_global_report()` has 6 INFERRED edges - model-reasoned connections that need verification._