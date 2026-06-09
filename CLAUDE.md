# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Custom Airtest test runner + scrcpy screen recorder for the **Screw Land** automation suite.

**NOT the Dagster orchestration framework** — "dagster" is only the repo/dir name. There is zero `import dagster`. The runner is built on Airtest (`airtest.core.api`, `airtest.report.report.LogToHtml`) plus the host `pixon` package.

Three runnable files (full prose guide: `README.md`):
- `dagster_run.py` — **primary** runner. Structured per-step logging + per-step HTML report + scrcpy recording.
- `pixon_run.py` — legacy minimal runner. Connects device, runs `.air`, no structured logging/report.
- `ScrcpyRecorder.py` — subprocess wrapper around `scrcpy-win64/scrcpy.exe` → MP4.

## Host dependency (critical — this repo is not self-running)

This repo is a tool meant to be checked out as the `dagster/` subdir of a **host project** (AutoRebase) that provides, one directory up:
- `../pixon/` — the automation package. `dagster_run.py` does `sys.path.insert(0, Path(__file__).parent.parent)` so `from pixon.common import test_flow` / `adb_utils` resolve to `../pixon`.
- `../Test/` — the `.air` test suites that get run.

A standalone clone (no sibling `pixon/` + `Test/`) will fail at `import pixon...`. The runner is intentionally non-invasive: it never writes into `../pixon/` or `../Test/`.

## Run

Run from the **host project root** (the parent of this dir), so `pixon` imports and `Test/...` paths resolve. CLI is **positional paths/globs only — no flags**. Device is auto-detected (`init_device()` → first ADB device).

```
# single test
python dagster/dagster_run.py Test/<Suite>/<tcNN_name>.air

# glob a suite (globs expanded internally; PowerShell-safe)
python dagster/dagster_run.py Test/HeartSystem/*.air

# multiple suites in one run
python dagster/dagster_run.py Test/DailyMission/*.air Test/HeartSystem/*.air

# legacy minimal runner
python dagster/pixon_run.py Test/<Suite>/<tcNN_name>.air
```

Recording defaults ON (`RECORDING = True`, `dagster_run.py`); console verbosity is `LOG_LEVEL = logging.DEBUG`. Toggle by editing those module constants.

## Output

Each test writes a timestamped folder under `report_run/` (gitignored):

```
report_run/<air_stem>_<YYYYMMDD_HHMMSS>/
  log.txt            # structured step log: "name: action, screenshot, status[, behaviour]"
  airtest.log        # Airtest NDJSON (LogToHtml input)
  report.html        # redirect → <stem>.log/report.html (Airtest's self-contained report)
  <stem>.log/        # bundled HTML + css/js/fonts
  *.jpg              # per-step screenshots
  recording_*.mp4    # scrcpy screen capture (if recording enabled)
```

## Architecture (non-obvious — spans runner + pixon)

- **`run_step()` monkey-patch** (`dagster_run.py`, `_hooked_run_step`, near top of module). Before any test module is imported, the runner wraps `pixon.common.test_flow.run_step`. Each call captures the step's name / action / status / screenshot / error into a global `_steps` list and emits an Airtest NDJSON `function` entry (`_emit_step_log`). This is *why* named steps and screenshots appear in `report.html` — tests just call `run_step(...)`; instrumentation is here, not in the tests. `_steps` is cleared per test → **sequential runs only**, not thread-safe.
- **Report pipeline** (`_generate_html`, `_normalize_airtest_depth`, `_write_log_txt`): normalizes NDJSON depth so steps render, appends a failure sentinel so failed runs show red, then calls `LogToHtml`. This area is mid-refactor — read the functions; do not assume the exact pipeline from this doc.
- **scrcpy lifecycle**: recorder `.start()` before the test, `.stop()` in a `finally`, MP4 path injected into the HTML report.

## Conventions

- scrcpy is **Windows-only** — binaries vendored in `scrcpy-win64/` (`scrcpy.exe`, bundled `adb.exe` + DLLs).
- Device serial is bound for the rest of the run via `pixon.common.adb_utils.set_default_serial` after connect.
- Page-object model, image templates, cheat endpoints, and `.env` config all live in the host `pixon` repo — see that project's docs, not here.
