#!/usr/bin/env python3
"""
Dagster — portable Airtest runner with structured step logging and HTML reports.

Execution Modes:
  - tester: (Default) Full recording, complete HTML reports with all game steps, and structured log.txt.
  - dev: Fast execution, filters out noisy game steps from HTML report to only show info/errors.

Non-invasive: does not write to the project's Test/ or pixon/ directories.
"""

import argparse
import glob as _glob
import sys
from pathlib import Path

# Add project root to path so pixon module can be imported,
# and dagster dir so sibling helpers (ScrcpyRecorder) resolve.
_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))

from airtest.core.api import connect_device, G  # noqa: E402 — import must follow sys.path.insert above

from dagster.capture.log_utils import setup_console_logging, LOG_LEVEL  # noqa: E402 — import must follow sys.path.insert above
from dagster.runner import run_single_test  # noqa: E402 — import must follow sys.path.insert above
from dagster.capture.step_capture import patch_run_step  # noqa: E402 — import must follow sys.path.insert above
from dagster.reports.aggregate_report import regenerate_global_report  # noqa: E402 — import must follow sys.path.insert above

def main():
    # 1. Setup Environment & Capture Hooks
    setup_console_logging(LOG_LEVEL)
    patch_run_step()

    from dagster.capture.error_capture import attach_error_handler
    attach_error_handler()  # pixon by default
    attach_error_handler("airtest")

    # 2. CLI Argument Parsing
    parser = argparse.ArgumentParser(description="Dagster runner")
    parser.add_argument("target", nargs="*", help="Paths or globs to .air projects (omit with --delete to only clean reports)")
    parser.add_argument("--device", type=str, default=None, help="Specific device serial to connect to")
    parser.add_argument("--shard-index", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--shard-total", type=int, default=1, help="Total number of shards")
    parser.add_argument("--mode", choices=["tester", "dev"], default="tester", help="Execution mode (tester=full artifacts, dev=filtered logs)")
    parser.add_argument("--delete", type=str, default=None, help="Delete report folders matching glob pattern (e.g. '*_20260630_*' or 'test_*')")
    parser.add_argument("--delete-older-than", type=int, default=None, help="Delete report folders older than N days")
    args, _ = parser.parse_known_args(sys.argv[1:])

    # 2b. Setup report directory (used for cleanup or test runs)
    report_root = _dagster_dir / "report_run"
    report_root.mkdir(parents=True, exist_ok=True)

    # 2c. Handle report cleanup if requested
    if args.delete or args.delete_older_than:
        from dagster.cleanup import delete_reports_by_pattern, delete_reports_older_than

        deleted_count = 0
        if args.delete:
            deleted_count += delete_reports_by_pattern(report_root, args.delete)
        if args.delete_older_than:
            deleted_count += delete_reports_older_than(report_root, args.delete_older_than)

        print(f"[INFO] Total reports deleted: {deleted_count}")
        sys.exit(0)

    # 3. Test Discovery
    if not args.target:
        sys.exit("[ERROR] target required when not using --delete or --delete-older-than")

    tests_set = set()
    for target in args.target:
        matches = _glob.glob(target, recursive=True)
        if not matches:
            matches = [target]
        for m in matches:
            p = Path(m).resolve()
            if p.is_dir() and p.suffix == ".air":
                tests_set.add(p)
            elif p.is_dir():
                for sub in p.rglob("*.air"):
                    if sub.is_dir():
                        tests_set.add(sub.resolve())
    tests = sorted(tests_set)
    if not tests:
        sys.exit(f"[ERROR] No .air projects found in: {args.target}")
        
    if args.shard_total > 1:
        tests = [t for i, t in enumerate(tests) if i % args.shard_total == args.shard_index]
        print(f"[INFO] Running shard {args.shard_index + 1}/{args.shard_total} ({len(tests)} tests)")

    # 4. Device Connection
    from dagster.device.device_manager import device_manager
    
    if args.device:
        caps = device_manager.check_health(args.device)
        if not caps:
            sys.exit(f"[ERROR] Device {args.device} is not healthy or not found.")
            
        uri = args.device if args.device.lower().startswith("android://") else f"Android://127.0.0.1:5037/{args.device}"
        uri += ("&" if "?" in uri else "?") + "cap_method=MINICAP&ori_method=ADBORI"
        connect_device(uri)
        device_id = args.device.rsplit("/", 1)[-1]
    else:
        healthy_devices = device_manager.get_healthy_devices()
        if not healthy_devices:
            sys.exit("[ERROR] No healthy devices found in pool.")
            
        # Try to align device with shard index if possible
        if len(healthy_devices) > args.shard_index:
            chosen = healthy_devices[args.shard_index]
        else:
            chosen = healthy_devices[0]
            print(f"[WARN] Not enough healthy devices for shard {args.shard_index}. Using device {chosen.serial}.")
            
        device_id = chosen.serial
        uri = f"Android://127.0.0.1:5037/{device_id}?cap_method=MINICAP&ori_method=ADBORI"
        connect_device(uri)

    from pixon.common.adb_utils import set_default_serial
    set_default_serial(device_id)

    # 6. Execute Tests
    run_had_failure = False
    for air_path in tests:
        py_scripts = [p for p in air_path.glob("*.py") if p.name != "__init__.py"]
        if not py_scripts:
            print(f"[WARN] {air_path.name}: no .py script found, skipping", file=sys.stderr)
            continue
        failed = run_single_test(air_path, py_scripts[0], args.mode, device_id, report_root)
        if failed:
            run_had_failure = True

    # 6b. Regenerate global aggregated report
    try:
        out = regenerate_global_report(report_root)
        print(f"[INFO] global report: {out}")
    except Exception as e:
        print(f"[WARN] global report generation failed: {e}", file=sys.stderr)

    # 7. Teardown
    try:
        G.DEVICE.disconnect()
    except Exception:
        pass

    if run_had_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
