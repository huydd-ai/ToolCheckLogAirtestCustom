import importlib
import sys
from datetime import datetime
from pathlib import Path

from airtest.core.api import auto_setup, G
from airtest.core.settings import Settings as ST

from dagster.reporting import write_log_txt, generate_html, generate_summary_report
from dagster.step_capture import clear_steps, get_steps


def run_single_test(air_path: Path, mode: str, device_id: str, report_root: Path, scrcpy_path: str) -> bool:
    """Run a single Airtest module, capture steps, video, and generate report. Returns True if failed."""
    module_name = air_path.stem
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = report_root / f"{air_path.stem}_{ts_str}"
    out_dir.mkdir(parents=True, exist_ok=True)

    auto_setup(str(air_path / f"{air_path.stem}.py"))
    ST.LOG_DIR = str(out_dir)
    G.LOGGER.set_logfile(str(out_dir / "airtest.log"))

    recorder = None
    recording_path = out_dir / f"recording_{device_id}_{module_name}.mp4"
    
    try:
        # pyrefly: ignore [missing-import]
        from ScrcpyRecorder import ScrcpyRecorder
        recorder = ScrcpyRecorder(output=str(recording_path), device=device_id, scrcpy_path=scrcpy_path)
        recorder.start()
    except Exception as e:
        print(f"[WARN] Failed to start recorder: {e}", file=sys.stderr)

    clear_steps()
    error_top = None
    status = "PASS"

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

        try:
            G.LOGGER.set_logfile(None)
        except Exception:
            pass

        # Compute final status once from captured steps; covers the case where
        # main() completed without exception but individual steps still failed.
        steps = get_steps()
        if status == "PASS" and any(s["status"] == "FAIL" for s in steps):
            status = "FAIL"

        recordings = sorted(out_dir.glob("recording_*.mp4"))

        try:
            generate_html(air_path, out_dir, mode, ndjson_name="airtest.log", recordings=recordings)
            print(f"[INFO] report.html generated")
        except Exception as e:
            print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

        try:
            summary_path = generate_summary_report(out_dir, air_path.stem, steps, status, recordings, error_top)
            print(f"[INFO] summary report: {summary_path.name}")
        except Exception as e:
            print(f"[WARN] Failed to generate summary report: {e}", file=sys.stderr)

        try:
            write_log_txt(out_dir, air_path.stem, steps, error_top)
            print(f"[INFO] log.txt written with {len(steps)} steps")
        except Exception as e:
            print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)

        print(f"Report: {out_dir}")
        print(f"[RESULT]\t{module_name}\t{status}\t{out_dir}")

    return status == "FAIL"
