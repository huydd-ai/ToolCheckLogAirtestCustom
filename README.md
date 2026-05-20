# Dagster — Airtest Runner + Scrcpy Recorder

Portable runner for Airtest `.air` projects with structured step logging, HTML reports, and optional scrcpy screen recording.

## Contents

| File | Purpose |
|------|---------|
| `dagster_run.py` | Main runner. Monkey-patches `run_step` to capture per-step status/screenshot/error → writes `log.txt` + `report.html`. |
| `pixon_run.py` | Minimal runner without structured logging. Useful for quick smoke runs. |
| `ScrcpyRecorder.py` | Subprocess wrapper around `scrcpy.exe` for Android screen recording (`.mp4`). |
| `scrcpy-win64/` | Vendored scrcpy v3.x Windows binaries (scrcpy.exe, adb.exe, dlls). |
| `report_run/` | Per-test output dirs (`log.txt`, `report.html`, `recording_*.mp4`). Gitignored. |

## Requirements

- Python ≥ 3.10
- Airtest 1.3.6 (`pip install airtest==1.3.6`)
- Android device with ADB authorized
- **`pixon.common.test_flow`** — `dagster_run.py` monkey-patches `run_step` on this module to intercept named steps. The runner expects `pixon/` to be importable (sibling checkout on `sys.path`, or installed package). See "Project context" below.

## Project context

This folder is extracted from the [AutoRebase](https://github.com/huydd-ai/AutoRebase) (private) Airtest test suite for the "Screw Land" game (Pixon Games). Tests live in `Test/*.air` directories and call `pixon.common.test_flow.run_step()` for instrumented steps.

To run dagster against external `.air` projects, ensure your tests:
1. Import `from pixon.common.test_flow import run_step` (or call via the module).
2. Wrap each instrumented action: `run_step("step name", action, *args)`.

Without the `pixon` package, dagster_run.py raises `ImportError` at module-load.

## Usage

```powershell
# Run a single .air test
python dagster_run.py path/to/test.air

# Run all .air under a directory
python dagster_run.py path/to/suite/

# Specific device
python dagster_run.py path/to/test.air --device emulator-5554

# Disable recording
python dagster_run.py path/to/test.air --no-recording
```

Output lands in `report_run/<test_stem>_<timestamp>/`:
- `log.txt` — structured step log: `name: action, screenshot, status[, error]`
- `report.html` — Airtest native HTML report
- `recording_<device>_<test>.mp4` — scrcpy capture (if `--recording`)

## Limitations

- Sequential test execution only (global `_steps` list, not thread-safe).
- Screenshot capture approximate: Airtest flushes asynchronously, so the captured image may be from the current or previous step.
- Windows-only scrcpy binary path (`scrcpy-win64/scrcpy.exe`). On Mac/Linux, recorder silently fails (`[WARN] Failed to start recorder`).
- `LogToHtml` requires `log.txt` at `log_root`; runner temporarily copies `report.json` → `log.txt` for HTML generation, then removes the copy.
