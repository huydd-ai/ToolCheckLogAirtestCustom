# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Custom Airtest test runner + scrcpy screen recorder for the **Screw Land** automation suite.

**NOT the Dagster orchestration framework** — "dagster" is only the repo/dir name. There is zero `import dagster`. The runner is built on Airtest (`airtest.core.api`) plus the host `pixon` package. (Per-run reports are a custom HTML page; Airtest's `LogToHtml` is no longer used.)

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

Run from the **host project root** (the parent of this dir), so `pixon` imports and `Test/...` paths resolve. CLI is **positional paths/globs only** (`--device <serial>` is an internal/child flag, not normally used).

**Auto multi-device parallelism:** with no `--device`, the runner enumerates connected ADB devices (`parallel_utils.list_devices`). With **≥2 devices** it splits the flows into balanced contiguous chunks (`parallel_utils.partition`, one chunk per device, fixed assignment) and spawns **one child process per device** (`_run_parallel` re-invokes this script with `--device <serial>` + that device's slice). Output streams live, each line prefixed `[serial]`; a combined summary is printed and written to `report_run/_parallel_<ts>/summary.txt`; the process exits non-zero if any flow failed. With **exactly 1 device** (or an explicit `--device`) it falls through to a single in-process sequential run. `--shard-total`/`--shard-index` still work and take precedence over auto-parallel.

**Self-update:** every invocation begins with a best-effort `git pull --ff-only` of `dagster/` from `origin/<current-branch>` (see `updater.py`). Opt out on dev boxes with `DAGSTER_NO_UPDATE=1` or by touching `dagster/.no-update`. Failures warn but never block the run.

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
  airtest.log        # Airtest NDJSON — parsed by runner for FAIL detection (not a report input)
  report.html        # custom self-contained per-run report (reporting.generate_summary_report)
  *.jpg              # per-step screenshots
  recording_*.mp4    # scrcpy screen capture (if recording enabled)
```

Multi-device runs additionally write `report_run/_parallel_<YYYYMMDD_HHMMSS>/summary.txt` (per-device flow results + exit code). Each child still produces its own per-flow `<stem>_<ts>/` folders as above.

## Architecture (non-obvious — spans runner + pixon)

- **`run_step()` monkey-patch** (`dagster_run.py`, `_hooked_run_step`, near top of module). Before any test module is imported, the runner wraps `pixon.common.test_flow.run_step`. Each call captures the step's name / action / status / screenshot / error into a global `_steps` list (and also emits an Airtest NDJSON entry via `_emit_step_log`, now used only for FAIL detection). The custom `report.html` is rendered from `_steps` — this is *why* named steps and screenshots appear; tests just call `run_step(...)`; instrumentation is here, not in the tests. `_steps` is cleared per test → **sequential runs only within a process**, not thread-safe. Multi-device parallelism is therefore **process-based** (one OS process per device, `_run_parallel`), never threaded: Airtest's `G.DEVICE` is a process-global singleton, so each device needs its own interpreter. The parent process holds no Airtest state — it only spawns children, streams their stdout, and aggregates `[RESULT]\t<flow>\t<status>\t<dir>` lines.
- **Report pipeline** (`reporting.py`): `generate_summary_report` builds a self-contained custom `report.html` (status banner, step table, screenshots, recordings) from the captured `_steps`; `write_log_txt` writes `log.txt`; shared dark theme in `report_theme.py`. Airtest's `LogToHtml` report was removed. `airtest.log` is still produced and parsed by `runner.py` (~lines 108-140) for traceback-based FAIL detection — do **not** delete it.
- **scrcpy lifecycle**: recorder `.start()` before the test, `.stop()` in a `finally`, MP4 path injected into the HTML report.

## Conventions

- scrcpy is **Windows-only** — binaries vendored in `scrcpy-win64/` (`scrcpy.exe`, bundled `adb.exe` + DLLs).
- Device serial is bound for the rest of the run via `pixon.common.adb_utils.set_default_serial` after connect.
- Page-object model, image templates, cheat endpoints, and `.env` config all live in the host `pixon` repo — see that project's docs, not here.
