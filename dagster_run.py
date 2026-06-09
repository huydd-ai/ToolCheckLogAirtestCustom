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
import subprocess
import sys
import threading
import time as _time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from parallel_utils import list_devices, partition

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
LOG_LEVEL: int = logging.DEBUG  # console verbosity (DEBUG for more detail)


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


def _normalize_airtest_depth(log_path: Path) -> None:
    """Promote NDJSON entry depths so the minimum becomes 1.

    LogToHtml only renders entries with depth==1. Pixon wrappers call airtest APIs
    one level deep, producing depth=2 entries that LogToHtml hides. Offset all
    depths so the outermost level becomes 1.
    """
    import json

    if not log_path.exists():
        return
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        depths: list[int] = []
        for ln in raw_lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                continue
            entries.append(obj)
            d = obj.get("depth")
            if isinstance(d, int):
                depths.append(d)
        if not depths:
            return
        offset = min(depths) - 1
        if offset <= 0:
            return
        for obj in entries:
            d = obj.get("depth")
            if isinstance(d, int):
                obj["depth"] = d - offset
        log_path.write_text(
            "\n".join(json.dumps(o, ensure_ascii=False) for o in entries) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[WARN] depth normalize failed: {e}", file=sys.stderr)


def _generate_html(
    air_path: Path,
    out_dir: Path,
    ndjson_name: str = "airtest.log",
    recordings: list[Path] | None = None,
    fail_message: str | None = None,
) -> None:
    """Generate Airtest HTML report from NDJSON log.

    Airtest's `export_dir` writes a self-contained `<stem>.log/` subdir with
    css/js/fonts bundled. We leave it intact (Airtest bakes relative paths into
    the embedded JSON), then write a redirect HTML at `out_dir/report.html` so
    the top-level file always opens the working report.

    `record_list` injects <video> tags into the HTML for screen recording playback.
    """
    try:
        from airtest.report.report import LogToHtml

        # Promote depth in NDJSON so LogToHtml's depth==1 filter shows our steps.
        _normalize_airtest_depth(out_dir / ndjson_name)

        # LogToHtml._analyse() checks only the LAST entry for traceback to set test_result.
        # Append a sentinel entry so failures surface correctly in the HTML status badge.
        if fail_message:
            import json as _json
            sentinel = {
                "tag": "function",
                "depth": 1,
                "time": _time.time(),
                "data": {
                    "name": "test_result",
                    "traceback": fail_message,
                    "log": fail_message,
                    "snapshot": False,
                    "call_args": {},
                },
            }
            ndjson_path = out_dir / ndjson_name
            with ndjson_path.open("a", encoding="utf-8") as f:
                f.write(_json.dumps(sentinel, ensure_ascii=False) + "\n")

        recordings = recordings or []
        record_list = [str(p) for p in recordings if p.exists()]

        log_to_html = LogToHtml(
            script_root=str(air_path),
            log_root=str(out_dir),
            logfile=ndjson_name,
            export_dir=str(out_dir),
            lang="en",
        )
        log_to_html.report(output_file="report.html", record_list=record_list)

        # Write redirect at top-level report.html → <stem>.log/report.html.
        exported = out_dir / f"{air_path.stem}.log"
        target_report = exported / "report.html"
        if not target_report.exists():
            target_report = exported / "log.html"
        if target_report.exists():
            redirect_rel = f"{exported.name}/{target_report.name}"
            (out_dir / "report.html").write_text(
                "<!DOCTYPE html><meta charset=\"utf-8\">"
                f"<meta http-equiv=\"refresh\" content=\"0; url={redirect_rel}\">"
                "<title>Redirecting...</title>"
                f"<p>If you are not redirected, <a href=\"{redirect_rel}\">click here</a>.</p>",
                encoding="utf-8",
            )
    except Exception as e:
        print(f"[WARN] Failed to generate HTML report: {e}", file=sys.stderr)


# ============================================================================
# PARALLEL ORCHESTRATOR
# ============================================================================

def _run_parallel(tests: list[Path], devices: list[str], report_root: Path) -> int:
    """Spawn one child `dagster_run.py --device <serial>` per device, stream their
    output live (prefixed [serial]), then print + write a combined summary.
    Returns the process exit code (1 if any flow failed or any child errored)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parallel_dir = report_root / f"_parallel_{ts}"
    parallel_dir.mkdir(parents=True, exist_ok=True)

    chunks = partition(tests, len(devices))
    assignments = [(dev, chunk) for dev, chunk in zip(devices, chunks) if chunk]

    print(f"[INFO] {len(tests)} flow(s) across {len(assignments)} device(s):")
    for dev, chunk in assignments:
        print(f"  {dev}: {', '.join(t.stem for t in chunk)}")

    print_lock = threading.Lock()
    results_lock = threading.Lock()
    results: list[dict] = []  # {serial, flow, status, dir}

    def reader(serial: str, proc: subprocess.Popen) -> None:
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.rstrip("\n")
            with print_lock:
                print(f"[{serial}] {line}")
            if line.startswith("[RESULT]\t"):
                parts = line.split("\t")
                if len(parts) == 4:
                    _, flow, status, rdir = parts
                    with results_lock:
                        results.append({"serial": serial, "flow": flow,
                                        "status": status, "dir": rdir})

    self_path = str(Path(__file__).resolve())
    procs: list[tuple[str, subprocess.Popen]] = []
    threads: list[threading.Thread] = []
    for serial, chunk in assignments:
        cmd = [sys.executable, self_path, *[str(t) for t in chunk], "--device", serial]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        th = threading.Thread(target=reader, args=(serial, proc), daemon=True)
        th.start()
        procs.append((serial, proc))
        threads.append(th)

    return_codes: dict[str, int] = {}
    for (serial, proc), th in zip(procs, threads):
        proc.wait()
        th.join()
        return_codes[serial] = proc.returncode

    failed = [r for r in results if r["status"] == "FAIL"]
    any_rc_error = any(rc != 0 for rc in return_codes.values())
    exit_code = 1 if (failed or any_rc_error) else 0

    lines = [f"=== RUN SUMMARY ({len(assignments)} devices, {len(tests)} flows) ==="]
    for serial, _chunk in assignments:
        cells = [f"{r['flow']} {r['status']}" for r in results if r["serial"] == serial]
        if cells:
            lines.append(f"{serial}  " + "  ".join(cells))
        else:
            lines.append(f"{serial}  (no results, rc={return_codes.get(serial, -1)})")
    lines.append(f"EXIT {exit_code} ({len(failed)} failed)")
    summary = "\n".join(lines)
    print(summary)
    (parallel_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return exit_code


# ============================================================================
# MAIN RUNNER
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dagster runner")
    parser.add_argument("target", nargs="+", help="Paths or globs to .air projects")
    parser.add_argument("--device", type=str, default=None, help="Specific device serial to connect to")
    parser.add_argument("--shard-index", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--shard-total", type=int, default=1, help="Total number of shards")
    args, _ = parser.parse_known_args(sys.argv[1:])

    raw_args = args.target

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
        
    # Shard the tests
    if args.shard_total > 1:
        tests = [t for i, t in enumerate(tests) if i % args.shard_total == args.shard_index]
        print(f"[INFO] Running shard {args.shard_index + 1}/{args.shard_total} ({len(tests)} tests)")

    # Setup device connection
    if args.device:
        uri = args.device if args.device.lower().startswith("android://") \
            else f"Android://127.0.0.1:5037/{args.device}"
        connect_device(uri)
        device_id = args.device.rsplit("/", 1)[-1]
    else:
        init_device()
        device_id = G.DEVICE.serialno

    from pixon.common.adb_utils import set_default_serial
    set_default_serial(device_id)

    # Setup output directory
    dagster_dir = Path(__file__).resolve().parent
    report_root = dagster_dir / "report_run"
    report_root.mkdir(parents=True, exist_ok=True)

    # Setup scrcpy recorder if enabled (binary lives next to this script)
    scrcpy_path = str(Path(__file__).resolve().parent / "scrcpy-win64" / "scrcpy.exe")

    # Run each test
    run_had_failure = False
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
                # pyrefly: ignore [missing-import]
                from ScrcpyRecorder import ScrcpyRecorder
                recorder = ScrcpyRecorder(output=str(recording_path), device=device_id, scrcpy_path=scrcpy_path)
                recorder.start()
            except Exception as e:
                print(f"[WARN] Failed to start recorder: {e}", file=sys.stderr)

        # Clear step capture for this test
        _steps.clear()
        error_top = None
        status = "PASS"

        # Run the test
        sys.path.insert(0, str(air_path))
        try:
            sys.modules.pop(module_name, None)
            mod = importlib.import_module(module_name)
            if hasattr(mod, "main"):
                mod.main()
                print(f"[PASS] {module_name}")
            else:
                status = "SKIP"
                print(f"[SKIP] {module_name} (no main function)")
        except Exception as e:
            error_top = e
            status = "FAIL"
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

            # Generate HTML report directly from airtest.log; inject recordings.
            try:
                recordings = sorted(out_dir.glob("recording_*.mp4"))
                fail_message = None
                if error_top:
                    fail_message = str(error_top)
                elif any(s["status"] == "FAIL" for s in _steps):
                    failed = next(s for s in _steps if s["status"] == "FAIL")
                    fail_message = failed.get("behaviour") or f"Step failed: {failed['name']}"
                _generate_html(
                    air_path,
                    out_dir,
                    ndjson_name="airtest.log",
                    recordings=recordings,
                    fail_message=fail_message,
                )
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
            # Promote to FAIL if any captured step failed (e.g. assertion inside main)
            if status == "PASS" and any(s["status"] == "FAIL" for s in _steps):
                status = "FAIL"
            if status == "FAIL":
                run_had_failure = True
            # Machine-readable result line for the parallel orchestrator to parse.
            print(f"[RESULT]\t{module_name}\t{status}\t{out_dir}")

    # Teardown
    try:
        G.DEVICE.disconnect()
    except Exception:
        pass

    if run_had_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
