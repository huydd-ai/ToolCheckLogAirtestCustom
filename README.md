# Dagster — Airtest Runner + Scrcpy Recorder

Portable, modular runner for Airtest `.air` projects with structured step logging, HTML reports, and scrcpy screen recording. It supports multiple execution modes for developers and testers.

## Contents

| File / Dir | Purpose |
|------------|---------|
| `dagster_run.py` | CLI Entrypoint. Handles test discovery, modes, and iterates through tests. |
| `step_capture.py` | Monkey-patches `run_step` to capture per-step status, screenshots, and errors. |
| `reporting.py` | Generates HTML reports and `log.txt`. Contains logic for filtering game step noise. |
| `runner.py` | The main test orchestration loop (`run_single_test`) with setup/teardown logic. |
| `log_utils.py` | Configures console output logging for Airtest/Poco. |
| `ScrcpyRecorder.py` | Subprocess wrapper around `scrcpy.exe` for Android screen recording (`.mp4`). |
| `scrcpy-win64/` | Vendored scrcpy v3.x Windows binaries (scrcpy.exe, adb.exe, dlls). |
| `report_run/` | Per-test output dirs (`log.txt`, `report.html`, `recording_*.mp4`). Gitignored. |

## Requirements

- Python ≥ 3.10
- Airtest 1.3.6 (`pip install airtest==1.3.6`)
- Android device with ADB authorized
- **`pixon.common.test_flow`** — `dagster_run.py` monkey-patches `run_step` on this module to intercept named steps. The runner expects `pixon/` to be importable (sibling checkout on `sys.path`, or installed package).

## Execution Modes

The runner operates in two main modes via the `--mode` flag:

1. **`tester` (Default)**: Comprehensive auditing. Generates a full HTML report with every game step logged (`touch`, `snapshot`, etc.), a full scrcpy video, and a structured `log.txt` of all steps.
2. **`dev`**: Fast debugging. Generates a clean HTML report that filters out noisy game steps, leaving only `info`, `error`, and exceptions. Skips `log.txt` generation, but still records a video.

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
- `log.txt` — structured step log: `name: action, screenshot, status[, error]` (Tester mode only)
- `report.html` — Airtest native HTML report
- `recording_<device>_<test>.mp4` — scrcpy capture

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
