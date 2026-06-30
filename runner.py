import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

from airtest.core.api import auto_setup, G
from airtest.core.settings import Settings as ST

from dagster.reporting import write_log_txt, generate_summary_report
from dagster.step_capture import clear_steps, get_steps
from dagster.OpenCVAnnotator import OpenCVAnnotator


def run_single_test(air_path: Path, py_script: Path, mode: str, device_id: str, report_root: Path) -> bool:
    """Run a single Airtest module, capture steps, video, and generate report. Returns True if failed."""
    module_name = py_script.stem

    from pixon.common.adb_utils import check_device_health
    if not check_device_health(device_id):
        print(f"[FAIL] {module_name} (Device {device_id} failed health check)", file=sys.stderr)
        return True

    t0 = time.time()
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = report_root / f"{air_path.stem}_{ts_str}"
    out_dir.mkdir(parents=True, exist_ok=True)

    auto_setup(str(py_script))
    ST.LOG_DIR = str(out_dir)
    G.LOGGER.set_logfile(str(out_dir / "airtest.log"))

    recorder = None
    recording_path = out_dir / f"recording_{device_id}_{module_name}.mp4"
    recordings = []
    
    try:
        from dagster.ScrcpyRecorder import ScrcpyRecorder
        recorder = ScrcpyRecorder(
            output=str(recording_path),
            fps=60,
            max_fps=60,
            max_width=480,
            bitrate=8_000_000,
            stay_awake=True,
            device=device_id or None,
        )
        recorder.start()
    except Exception as e:
        print(f"[WARN] Failed to start recorder: {e}", file=sys.stderr)

    from dagster.error_capture import clear_errors
    clear_errors()
    clear_steps()
    OpenCVAnnotator.reset(test_name=module_name)
    error_top = None
    status = "PASS"

    try:
        import runpy
        from pixon.common.adb_errors import AdbDeviceOfflineError
        
        max_test_retries = 2
        for attempt in range(max_test_retries):
            try:
                mod = runpy.run_path(str(py_script))
                if "main" in mod:
                    mod["main"]()
                    status = "PASS"
                    print(f"[PASS] {module_name}")
                else:
                    status = "SKIP"
                    print(f"[SKIP] {module_name} (no main function)")
                break  # Exit retry loop on success or skip
            except AdbDeviceOfflineError as e:
                print(f"[WARN] Device {device_id} disconnected during {module_name} (attempt {attempt + 1}/{max_test_retries}). Waiting 10s...", file=sys.stderr)
                if attempt < max_test_retries - 1:
                    time.sleep(10)
                    for wait_attempt in range(4):
                        try:
                            from airtest.core.api import connect_device
                            uri = f"Android://127.0.0.1:5037/{device_id}?cap_method=MINICAP&ori_method=ADBORI"
                            connect_device(uri)
                            if check_device_health(device_id):
                                print(f"[INFO] Device {device_id} recovered successfully.", file=sys.stderr)
                                break
                        except Exception as conn_err:
                            print(f"[WARN] Reconnect attempt {wait_attempt+1} failed: {conn_err}", file=sys.stderr)
                        time.sleep(5)
                    continue
                else:
                    error_top = e
                    status = "FAIL"
                    print(f"[FAIL] {module_name} (Device Offline): {e}")
                    break
            except Exception as e:
                error_top = e
                status = "FAIL"
                print(f"[FAIL] {module_name}: {e}")
                break
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

        try:
            annotator = OpenCVAnnotator()
            annotated_path = out_dir / f"recording_{device_id}_{module_name}_steps.mp4"
            annotator.finalize(status, annotated_path)
        except Exception as e:
            print(f"[WARN] Failed to create step highlights video: {e}", file=sys.stderr)

        try:
            G.LOGGER.set_logfile(None)
        except Exception:
            pass

        # Compute final status once from captured steps; covers the case where
        # main() completed without exception but individual steps still failed.
        steps = get_steps()
        if status == "PASS" and any(s["status"] == "FAIL" for s in steps):
            status = "FAIL"

        from dagster.error_capture import get_errors
        errors = get_errors()
        if errors and status == "PASS":
            status = "FAIL"

        if errors and error_top is None:
            error_top = RuntimeError(errors[0]["msg"])

        for err in errors:
            if any(s.get("behaviour") == err["msg"] for s in steps):
                continue
            steps.append({
                "name": f"[ERROR] {err.get('step') or err['logger']}",
                "action": "logged_error",
                "status": "FAIL",
                "screenshot": err.get("screenshot"),
                "behaviour": err["msg"],
                "duration": 0,
            })

        airtest_log = out_dir / "airtest.log"
        if airtest_log.exists():
            import json
            try:
                for line in airtest_log.read_text(encoding="utf-8").splitlines():
                    if not line.strip(): continue
                    try:
                        obj = json.loads(line)
                        data_dict = obj.get("data", {})
                        tb = data_dict.get("traceback")
                        if tb:
                            if status == "PASS":
                                status = "FAIL"
                            err_msg = tb.strip().split('\n')[-1]
                            if error_top is None:
                                error_top = RuntimeError(err_msg)
                            if not any(s.get("behaviour") == err_msg for s in steps):
                                step_name = data_dict.get("name") or "[ERROR] Airtest Assertion"
                                last_screen = next(
                                    (s["screenshot"] for s in reversed(steps) if s.get("screenshot")), None
                                )
                                steps.append({
                                    "name": step_name,
                                    "action": "assert_failed",
                                    "status": "FAIL",
                                    "screenshot": last_screen,
                                    "behaviour": err_msg,
                                    "duration": 0,
                                })
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"[WARN] Failed to parse airtest.log: {e}", file=sys.stderr)

        recordings = [*recordings, *sorted(out_dir.glob("recording_*.mp4"))]

        airtest_log_text = None
        if airtest_log.exists():
            try:
                airtest_log_text = airtest_log.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        elapsed = time.time() - t0
        try:
            report_path = generate_summary_report(
                out_dir, air_path.stem, steps, status, recordings, error_top,
                airtest_log=airtest_log_text, elapsed=elapsed,
            )
            print(f"[INFO] report: {report_path.name}")
        except Exception as e:
            print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

        try:
            write_log_txt(out_dir, air_path.stem, steps, error_top, air_path=air_path, device_id=device_id)
            print(f"[INFO] log.txt written with {len(steps)} steps")
        except Exception as e:
            print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)

        print(f"Report: {out_dir}")
        print(f"[RESULT]\t{module_name}\t{status}\t{out_dir}")

    return status == "FAIL"
