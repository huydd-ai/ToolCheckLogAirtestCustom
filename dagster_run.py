#!/usr/bin/env python3
"""
Dagster — portable Airtest runner with structured step logging and HTML reports.

Runs .air test cases, captures named steps from run_step(), and exports:
  - log.txt: structured format "name: action, screenshot, status[, behaviour]"
  - report.html: Airtest's native HTML report
  - *.jpg: screenshots captured during test execution

Non-invasive: does not write to the project's Test/ or pixon/ directories.
"""

import glob as _glob
import importlib
import logging
import sys
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Add project root to path so pixon module can be imported,
# and dagster dir so sibling helpers (ScrcpyRecorder) resolve.
_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_dagster_dir))

# ============================================================================
# STEP CAPTURE - Monkey-patch before any test module import
# Must happen here (module level) so the patch is in place before any test
# module is imported. _steps is global and cleared per test — sequential only.
# ============================================================================

from pixon.common import test_flow as _tf

_steps: list[dict] = []
_orig_run_step = _tf.run_step

def _emit_step_log(name: str, action_name: str, start: float, end: float, ret: Any, traceback: str | None) -> None:
    """Emit an Airtest NDJSON 'function' entry so LogToHtml can show the step in report.html."""
    try:
        from airtest.core.helper import G as _G
        data: dict[str, Any] = {
            "name": name,
            "call_args": {"action": action_name},
            "start_time": start,
            "end_time": end,
            "ret": ret,
        }
        if traceback is not None:
            data["traceback"] = traceback
        _G.LOGGER.log("function", depth=1, data=data)
    except Exception:
        pass  # logger may not be initialized yet (e.g. before auto_setup)


def _snapshot_step(name: str) -> str | None:
    """Take an Airtest snapshot tied to the step name so HTML binds an image to the step."""
    try:
        from airtest.core.api import snapshot as _snap
        result = _snap(msg=name)
        if isinstance(result, dict):
            return result.get("screen")
        return None
    except Exception:
        return None


def _hooked_run_step(name: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Intercept run_step calls to capture step name, action, status, screenshot, and error."""
    action_name = getattr(action, "__name__", str(action))
    step = {
        "name": name,
        "action": action_name,
        "status": None,
        "screenshot": None,
        "behaviour": None,
    }
    start = _time.time()
    try:
        result = _orig_run_step(name, action, *args, **kwargs)
        screen_path = _snapshot_step(name)
        step["status"] = "PASS"
        step["screenshot"] = screen_path or _latest_screenshot()
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=None)
        return result
    except Exception as exc:
        screen_path = _snapshot_step(name)
        step["status"] = "FAIL"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["behaviour"] = str(exc)
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=str(exc))
        raise

_tf.run_step = _hooked_run_step


# ============================================================================
# AIRTEST SETUP - Now safe to import Airtest and test modules
# ============================================================================

from airtest.core.api import *
from airtest.core.settings import Settings as ST


# ============================================================================
# CONFIG
# ============================================================================

RECORDING: bool = True  # scrcpy screen recording (set False to disable)
LOG_LEVEL: int = logging.INFO  # console verbosity (DEBUG for more detail)


# ============================================================================
# CONSOLE LOGGING - Stream Airtest's internal logs to stdout
# ============================================================================

def _setup_console_logging(level: int = logging.INFO) -> None:
    """Attach a stdout StreamHandler to Airtest's loggers so steps print to CLI."""
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.setLevel(level)
    # Cover Airtest + Poco namespaces; root left untouched to avoid 3rd-party noise.
    for logger_name in ("airtest", "poco"):
        lg = logging.getLogger(logger_name)
        lg.setLevel(level)
        # Avoid duplicate handlers on re-entry
        if not any(isinstance(h, logging.StreamHandler) for h in lg.handlers):
            lg.addHandler(handler)
        lg.propagate = False


_setup_console_logging(LOG_LEVEL)


# ============================================================================
# HELPERS
# ============================================================================

def _latest_screenshot() -> str | None:
    """Find the most recently modified .jpg/.png in ST.LOG_DIR."""
    d = Path(ST.LOG_DIR) if ST.LOG_DIR else None
    if not d or not d.exists():
        return None
    # Look for both .jpg and .png
    imgs = sorted(
        list(d.glob("*.jpg")) + list(d.glob("*.png")),
        key=lambda p: p.stat().st_mtime,
    )
    return imgs[-1].name if imgs else None


def _write_log_txt(out_dir: Path, tc_name: str, steps: list[dict], error_top: Exception | None) -> None:
    """Write structured log.txt from captured steps."""
    log_file = out_dir / "log.txt"

    # Determine overall status
    overall_status = "FAIL" if error_top or any(s["status"] == "FAIL" for s in steps) else "PASS"

    lines = [
        f"# {tc_name}",
        f"# Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Status: {overall_status}",
        "",
    ]

    for step in steps:
        screenshot = step["screenshot"] or "-"
        # Clean up step name (remove trailing newlines/whitespace)
        clean_name = step['name'].strip()
        base_line = f"{clean_name}: {step['action']}, {screenshot}, {step['status']}"

        if step["behaviour"]:
            lines.append(f"{base_line}, {step['behaviour']}")
        else:
            lines.append(base_line)

    if error_top and not steps:
        # Top-level error with no named steps captured
        lines.append(f"ERROR: {str(error_top)}")

    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_html(air_path: Path, out_dir: Path, ndjson_name: str = "airtest.log") -> None:
    """Generate Airtest HTML report from NDJSON log.

    LogToHtml reads <log_root>/<logfile>, renders the template, and writes report.html.
    `export_dir` triggers bundling of static assets (css/js/fonts) into the output dir
    so the report is self-contained and viewable offline.
    """
    try:
        from airtest.report.report import LogToHtml

        log_to_html = LogToHtml(
            script_root=str(air_path),
            log_root=str(out_dir),
            logfile=ndjson_name,
            export_dir=str(out_dir),
            lang="en",
        )
        log_to_html.report(output_file=str(out_dir / "report.html"))
    except Exception as e:
        print(f"[WARN] Failed to generate HTML report: {e}", file=sys.stderr)


# ============================================================================
# MAIN RUNNER
# ============================================================================

def main():
    raw_args = sys.argv[1:]
    if not raw_args:
        sys.exit(
            "usage: python dagster_run.py <path-or-glob> [<path-or-glob> ...]\n"
            "  ex: python dagster_run.py Test/DailyMission/tc01_*.air\n"
            "      python dagster_run.py Test/DailyMission/*\n"
            "      python dagster_run.py Test/*/*"
        )

    # Expand globs internally (PowerShell does not auto-expand)
    paths: list[Path] = []
    for a in raw_args:
        if any(c in a for c in "*?["):
            matches = _glob.glob(a, recursive=True)
            if not matches:
                print(f"[WARN] no match for glob: {a}", file=sys.stderr)
                continue
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(a))

    # Discover .air test projects
    tests: list[Path] = []
    for p in paths:
        p = p.resolve()
        if p.suffix == ".air" and p.exists():
            tests.append(p)
        elif p.is_dir():
            found = sorted(p.glob("*.air")) or sorted(p.rglob("*.air"))
            tests.extend(found)

    # Dedupe, keep order
    seen: set[Path] = set()
    tests = [t for t in tests if not (t in seen or seen.add(t))]

    if not tests:
        sys.exit(f"[ERROR] No .air projects found in: {raw_args}")

    # Setup device connection (auto-detect first ADB device)
    init_device()
    device_id = G.DEVICE.serialno

    # Setup output directory
    dagster_dir = Path(__file__).resolve().parent
    report_root = dagster_dir / "report_run"
    report_root.mkdir(parents=True, exist_ok=True)

    # Setup scrcpy recorder if enabled (binary lives next to this script)
    scrcpy_path = str(Path(__file__).resolve().parent / "scrcpy-win64" / "scrcpy.exe")

    # Run each test
    for air_path in tests:
        air_py = air_path / f"{air_path.stem}.py"
        if not air_py.exists():
            continue

        module_name = air_path.stem

        # Create output directory for this test run
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = report_root / f"{air_path.stem}_{ts_str}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Setup Airtest for this test
        auto_setup(str(air_py))

        # Redirect Airtest logging + screenshots to dagster output dir.
        # NDJSON goes to airtest.log (LogToHtml input); dagster's structured log goes to log.txt.
        ST.LOG_DIR = str(out_dir)
        G.LOGGER.set_logfile(str(out_dir / "airtest.log"))

        # Setup recording
        recorder = None
        recording_path = out_dir / f"recording_{device_id}_{module_name}.mp4"
        if RECORDING:
            try:
                from ScrcpyRecorder import ScrcpyRecorder
                recorder = ScrcpyRecorder(output=str(recording_path), device=device_id, scrcpy_path=scrcpy_path)
                recorder.start()
            except Exception as e:
                print(f"[WARN] Failed to start recorder: {e}", file=sys.stderr)

        # Clear step capture for this test
        _steps.clear()
        error_top = None

        # Run the test
        sys.path.insert(0, str(air_path))
        try:
            sys.modules.pop(module_name, None)
            mod = importlib.import_module(module_name)
            if hasattr(mod, "main"):
                mod.main()
                print(f"[PASS] {module_name}")
            else:
                print(f"[SKIP] {module_name} (no main function)")
        except Exception as e:
            error_top = e
            print(f"[FAIL] {module_name}: {e}")
        finally:
            if recorder:
                try:
                    recorder.stop()
                except Exception as e:
                    print(f"[WARN] recorder stop: {e}", file=sys.stderr)
            sys.path.remove(str(air_path))

            # Close Airtest logger to flush remaining entries
            try:
                G.LOGGER.set_logfile(None)
            except Exception:
                pass

            # Generate HTML report directly from airtest.log (no rename dance).
            try:
                _generate_html(air_path, out_dir, ndjson_name="airtest.log")
                print(f"[INFO] report.html generated")
            except Exception as e:
                print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

            # Write our structured log.txt
            try:
                _write_log_txt(out_dir, air_path.stem, _steps, error_top)
                print(f"[INFO] log.txt written with {len(_steps)} steps")
            except Exception as e:
                print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)

            print(f"Report: {out_dir}")

    # Teardown
    try:
        G.DEVICE.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    main()
