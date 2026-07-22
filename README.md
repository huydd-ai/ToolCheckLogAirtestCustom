# Dagster — Airtest Runner + Scrcpy Recorder + Puzzle Game Benchmark Engine

Portable, modular test runner and benchmark engine for Airtest `.air` projects with structured step logging, HTML reports, scrcpy screen recording, and a **Real-time 12-Parameter Puzzle Game Benchmark Dashboard**.

---

## Contents & Architecture

| File / Dir | Purpose |
|------------|---------|
| `dagster_run.py` | CLI Entrypoint. Handles test discovery, modes, and iterates through tests. |
| `report_server.py` | Local HTTP server (`python dagster/report_server.py --port 7070`) serving the dashboard and handling live telemetry, rerun, and run APIs. |
| `runner.py` | Main test orchestration loop (`run_single_test`) with setup/teardown logic. |
| `benchmark.py` | Airtest Puzzle Game Benchmark engine evaluating 12 standard parameters and enforcing mode action triggers. |
| `config.py` | Path constants (`get_paths()`: project root, `pixon/`, `Test/`). |
| `cleanup.py` | Deletes `report_run/` folders by glob pattern or age. |
| `capture/performance_probe.py` | Background thread sampling live FPS (`dumpsys gfxinfo`) and RAM (`dumpsys meminfo`). |
| `capture/step_capture.py` | Monkey-patches `run_step` to capture per-step status, screenshots, and errors. |
| `capture/error_capture.py` | Captures ERROR/CRITICAL log records for the per-run error panel. |
| `capture/log_utils.py` | Configures console output logging for Airtest/Poco. |
| `reports/reporting.py` | Generates the per-run custom `report.html` and `log.txt`. |
| `reports/report_theme.py` | Shared dark-theme CSS (`THEME_CSS`) inlined into both the dashboard and per-run report. |
| `reports/report_data.py` | Parses run folders, computes metrics (trend, flaky detection), builds the test catalog. |
| `reports/aggregate_report.py` | Generates the global `report.html` dashboard, aggregating all test runs by date. |
| `recording/ScrcpyRecorder.py` | Subprocess wrapper around `scrcpy.exe` for Android screen recording (`.mp4`). |
| `recording/OpenCVRecorder.py`, `recording/OpenCVAnnotator.py` | Alternate OpenCV-based capture/annotation path. |
| `device/device_manager.py` | Discovers ADB devices, probes health, and puts devices in `adb root` mode to eliminate emulator popup toasts. |
| `device/ldplayer_ctl.py` | Launches/closes the LDPlayer emulator on Windows. |
| `static/metric_guide.json` | Single source of truth for the 12 Airtest Puzzle Game benchmark metric definitions, formulas, and remediation plans. |
| `static/index.html` & `app.js` | Real-time dashboard with Alpine.js, 4 category cards, live device manager, and metric guide modals. |
| `tests/` | Unit tests (`test_benchmarks.py`, `test_report_data.py`, `test_ldplayer_ctl.py`, `test_report_server.py`). |
| `scrcpy-win64/` | Vendored scrcpy v3.x Windows binaries (scrcpy.exe, adb.exe, dlls). |
| `report_run/` | Per-test output dirs (`log.txt`, `report.html`, `recording_*.mp4`). Gitignored. |

---

## 🎯 Puzzle Game Benchmark System (12 Standard Parameters)

The benchmark system evaluates automated test runs against 12 standard parameters across 4 categories:

### I. Nhóm Chỉ Số Hiệu Năng Game (Game Performance)
1. **Average FPS (`avg_fps`)**: $\text{Avg FPS} = \frac{\text{Total Frames}}{\text{Total Duration (s)}}$. Target: $\ge 55$ FPS (dumpsys gfxinfo).
2. **Combo FPS Drop Delta (`combo_drop_fps`)**: $\Delta \text{FPS}_{\text{combo}} = \text{FPS}_{\text{Idle}} - \text{FPS}_{\text{Min (Combo)}}$. Target: $\le 5$ FPS.
3. **Memory Leak Coefficient (`r_leak_mb_hr`)**: $R_{\text{leak}} = \frac{\text{RAM}_{\text{end}} - \text{RAM}_{\text{start}}}{\text{Duration (hr)}}$. Target: $< 15$ MB/hr (dumpsys meminfo).
4. **Asset Loading Failure Rate (`a_fail_pct`)**: $P_{\text{asset\_fail}} = \left( \frac{\text{Asset Errors}}{\text{Total Assets}} \right) \times 100\%$. Target: $0\%$.

### II. Nhóm Độ Ổn Định Hệ Thống & Giả Lập (Emulator Stability)
5. **Game Crash / ANR Rate (`r_crash_pct`)**: $R_{\text{crash}} = \left( \frac{\text{Total Crash + ANR}}{\text{Total Levels}} \right) \times 100\%$. Target: $< 0.5\%$.
6. **Automation Softlock Rate (`r_softlock_pct`)**: $R_{\text{softlock}} = \left( \frac{\text{Stuck > 30s Count}}{\text{Total Moves}} \right) \times 100\%$. Target: $< 1.0\%$.
7. **Emulator RAM Leak (`delta_ram_emu_mb_hr`)**: $\Delta \text{RAM}_{\text{Emu}} = \frac{\text{RAM}_{\text{Emu End}} - \text{RAM}_{\text{Emu Start}}}{\text{Duration (hr)}}$. Target: $< 50$ MB/hr (dnplayer.exe).
8. **Multi-Instance Scaling Efficiency (`e_scaling_pct`)**: $E_{\text{scaling}} = \left( \frac{\text{Duration (Single)}}{\text{Avg Duration (Multi)}} \right) \times 100\%$. Target: $\ge 85\%$.

### III. Nhóm Chất Lượng Script Automation (Airtest / Poco Quality)
9. **Image Match Time (`t_match_ms`)**: $T_{\text{match}} = T_{\text{Found Coords}} - T_{\text{Capture Start}}$. Target: $< 200$ ms (OpenCV).
10. **CV Identification Error Rate (`r_cv_error_pct`)**: $R_{\text{CV\_error}} = \left( \frac{\text{Wrong Match}}{\text{Total Scans}} \right) \times 100\%$. Target: $0\%$.
11. **Input Latency (`t_input_latency_ms`)**: $T_{\text{latency}} = T_{\text{Pixel Color Change}} - T_{\text{touch()}}$. Target: $< 120$ ms.
12. **Critical Path Coverage (`c_critical_pct`)**: $C_{\text{critical}} = \left( \frac{\text{Automated Core}}{\text{Total GDD Core}} \right) \times 100\%$. Target: $100\%$.

---

## ⚡ Key Real-Time Dashboard Features

- **Live Device Running Uptime Counter**: Automatically tracks device running duration (`⏱️ UPTIME: MM:SS`) when target devices turn ON, resetting to `0` when disconnected.
- **ADB Root Daemon Integration**: Runs `adb root` natively on target devices to eliminate Superuser prompt popups and notification banners on emulator screens.
- **Adaptive Polling Loop**: Dynamic 2s polling during active test execution, scaling back to 10s idle refresh, auto-refetching instantly on tab focus.
- **Evaluation Modes**: Switch between `Normal Baseline Mode` and `Aggressive Strict Mode` with automated enforcement action triggers (`HALT_BUILD`, `OPTIMIZE_GRAPHICS`, `REFACTOR_SCRIPTS`, `RESTART_EMULATOR`, `SCALE_INFRASTRUCTURE`).

---

## Requirements

- Python ≥ 3.10
- Airtest 1.3.6 (`pip install airtest==1.3.6`)
- Android device or emulator (LDPlayer, BlueStacks, Nox, Android Studio) with ADB authorized
- **`pixon.common.test_flow`** — `dagster_run.py` monkey-patches `run_step` on this module to intercept named steps.

---

## Usage

```powershell
# Run a single .air test in tester mode (default)
python dagster_run.py path/to/test.air

# Run all .air under a directory
python dagster_run.py path/to/suite/

# Start the local real-time dashboard server
python dagster/report_server.py --port 7070
```

Open dashboard in browser: [http://localhost:7070/](http://localhost:7070/)
