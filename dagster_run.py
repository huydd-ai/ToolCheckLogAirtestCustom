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
import shutil
import sys
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

def _hooked_run_step(name: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Intercept run_step calls to capture step name, action, status, screenshot, and error."""
    step = {
        "name": name,
        "action": getattr(action, "__name__", str(action)),
        "status": None,
        "screenshot": None,
        "behaviour": None,
    }
    try:
        result = _orig_run_step(name, action, *args, **kwargs)
        step["status"] = "PASS"
        # Screenshot is approximate: Airtest flushes async, so this captures
        # the most recent image at call time, which may be from this step or
        # the previous one.
        step["screenshot"] = _latest_screenshot()
        _steps.append(step)
        return result
    except Exception as exc:
        step["status"] = "FAIL"
        step["screenshot"] = _latest_screenshot()
        step["behaviour"] = str(exc)
        _steps.append(step)
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


def _generate_html(air_path: Path, out_dir: Path) -> None:
    """Generate Airtest HTML report from NDJSON log."""
    try:
        from airtest.report.report import LogToHtml

        # LogToHtml needs script_root (for template images) and log_root (for log.txt)
        # It will find log.txt at log_root/log.txt
        log_to_html = LogToHtml(
            script_root=str(air_path),
            log_root=str(out_dir),
        )
        log_to_html.report(output_file=str(out_dir / "report.html"))
    except Exception as e:
        # Silently skip HTML generation if it fails — log.txt is the primary output
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

        # Redirect Airtest logging to dagster output directory
        # Use report.json for Airtest's NDJSON so we can use log.txt for our structured format
        ST.LOG_DIR = str(out_dir)
        G.LOGGER.set_logfile(str(out_dir / "report.json"))

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

            # Generate HTML report — LogToHtml expects log.txt, so copy report.json
            # there temporarily, generate, then remove the copy.
            try:
                report_json = out_dir / "report.json"
                tmp_log = out_dir / "log.txt"
                if report_json.exists():
                    shutil.copy2(report_json, tmp_log)
                _generate_html(air_path, out_dir)
                print(f"[INFO] report.html generated")
                if tmp_log.exists():
                    tmp_log.unlink()
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
