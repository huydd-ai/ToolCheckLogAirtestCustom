# Dagster — Airtest Runner + Scrcpy Recorder

Portable, modular runner for Airtest `.air` projects with structured step logging, HTML reports, and scrcpy screen recording. It supports multiple execution modes for developers and testers.

## Contents

| File / Dir | Purpose |
|------------|---------|
| `dagster_run.py` | CLI Entrypoint. Handles test discovery, modes, and iterates through tests. |
| `step_capture.py` | Monkey-patches `run_step` to capture per-step status, screenshots, and errors. |
| `reporting.py` | Generates the per-run custom `report.html` and `log.txt`. |
| `report_theme.py` | Shared dark-theme CSS (`THEME_CSS`) inlined into both the dashboard and per-run report. |
| `runner.py` | The main test orchestration loop (`run_single_test`) with setup/teardown logic. |
| `log_utils.py` | Configures console output logging for Airtest/Poco. |
| `ScrcpyRecorder.py` | Subprocess wrapper around `scrcpy.exe` for Android screen recording (`.mp4`). |
| `scrcpy-win64/` | Vendored scrcpy v3.x Windows binaries (scrcpy.exe, adb.exe, dlls). |
| `aggregate_report.py` | Generates the global `report.html` dashboard, aggregating all test runs by date. |
| `report_server.py` | Local HTTP server (`python report_server.py`) serving the dashboard and handling delete APIs. |
| `report_run/` | Per-test output dirs (`log.txt`, `report.html`, `recording_*.mp4`). Gitignored. |

## Requirements

- Python ≥ 3.10
- Airtest 1.3.6 (`pip install airtest==1.3.6`)
- Android device with ADB authorized
- **`pixon.common.test_flow`** — `dagster_run.py` monkey-patches `run_step` on this module to intercept named steps. The runner expects `pixon/` to be importable (sibling checkout on `sys.path`, or installed package).

## Execution Modes

The per-run report is a custom, self-contained `report.html` built from the captured named steps (`run_step(...)` calls), plus `log.txt`, per-step screenshots, and a scrcpy video.

The `--mode` flag (`tester` default, `dev`) is **currently vestigial**: it used to filter the old Airtest report's step noise, but that report was replaced by the custom one, so both modes now produce identical output. Kept for CLI compatibility.

## Usage

```powershell
# Run a single .air test in tester mode (default)
python dagster_run.py path/to/test.air

# Run a test in dev mode (filtered HTML reports, no step spam)
python dagster_run.py path/to/test.air --mode dev

# Run all .air under a directory
python dagster_run.py path/to/suite/

# Specific device
python dagster_run.py path/to/test.air --device emulator-5554
```

Output lands in `report_run/<test_stem>_<timestamp>/`:
- `log.txt` — structured step log: `name: action, screenshot, status[, error]`
- `report.html` — custom self-contained per-run report (status banner, step table, screenshots, recordings)
- `airtest.log` — Airtest NDJSON; parsed by the runner for FAIL detection (not a report input)
- `recording_<device>_<test>.mp4` — scrcpy capture

### Global Dashboard

You can view a centralized dashboard of all test runs across all dates. It provides a rich UI with pass/fail summary metrics, name search and status filters, per-run reports in a modal, rerun, and mass-delete of old reports. Long test names and verbose error messages gracefully word-wrap to prevent UI overflow.

```powershell
# Start the local server
python dagster/report_server.py --port 7070

# Open in your browser:
# http://localhost:7070/
```

### Self-update

Each invocation of `dagster_run.py` starts with a best-effort `git pull --ff-only` against `origin/<current-branch>`. Test machines stay current automatically; the run continues even if the pull fails (network down, missing git binary, non-fast-forward).

To disable the auto-update on a dev machine, do **either** of:

- Set the environment variable `DAGSTER_NO_UPDATE=1`, **or**
- Create an empty file `dagster/.no-update` (gitignored).

Parallel multi-device runs only pull in the parent process; children invoked with `--device <serial>` skip the update so that N devices do not trigger N concurrent pulls.

## Limitations

- Sequential test execution only (global `_steps` list, not thread-safe).
- Screenshot capture approximate: Airtest flushes asynchronously, so the captured image may be from the current or previous step.
- Windows-only scrcpy binary path (`scrcpy-win64/scrcpy.exe`). On Mac/Linux, recorder silently fails (`[WARN] Failed to start recorder`).
