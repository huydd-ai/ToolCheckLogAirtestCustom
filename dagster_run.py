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

from parallel_utils import list_devices, partition

# Add project root to path so pixon module can be imported,
# and dagster dir so sibling helpers (ScrcpyRecorder) resolve.
_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_dagster_dir))

from airtest.core.api import connect_device, init_device, G

from dagster.log_utils import setup_console_logging, LOG_LEVEL
from dagster.runner import run_single_test
from dagster.step_capture import patch_run_step
from dagster.aggregate_report import regenerate_global_report

def main():
    # 1a. Self-update from origin (best-effort, never blocks the run).
    # Parent-only: when --device <serial> is in argv we are a parallel child
    # and the parent already pulled - skip to avoid concurrent `git pull`.
    from dagster.updater import check_and_update
    check_and_update(repo_root=_dagster_dir, is_parallel_child=("--device" in sys.argv))

    # 1b. Setup Environment & Capture Hooks
    setup_console_logging(LOG_LEVEL)
    patch_run_step()

    from dagster.error_capture import attach_error_handler
    attach_error_handler()  # pixon by default
    attach_error_handler("airtest")

    # 2. CLI Argument Parsing
    parser = argparse.ArgumentParser(description="Dagster runner")
    parser.add_argument("target", nargs="+", help="Paths or globs to .air projects")
    parser.add_argument("--device", type=str, default=None, help="Specific device serial to connect to")
    parser.add_argument("--shard-index", type=int, default=0, help="Shard index (0-indexed)")
    parser.add_argument("--shard-total", type=int, default=1, help="Total number of shards")
    parser.add_argument("--mode", choices=["tester", "dev"], default="tester", help="Execution mode (tester=full artifacts, dev=filtered logs)")
    args, _ = parser.parse_known_args(sys.argv[1:])

    # 3. Test Discovery
    paths: list[Path] = []
    for a in args.target:
        if any(c in a for c in "*?["):
            matches = _glob.glob(a, recursive=True)
            if not matches:
                print(f"[WARN] no match for glob: {a}", file=sys.stderr)
                continue
            paths.extend(Path(m) for m in matches)
        else:
            paths.append(Path(a))

    tests: list[Path] = []
    for p in paths:
        p = p.resolve()
        if p.suffix == ".air" and p.exists():
            tests.append(p)
        elif p.is_dir():
            found = sorted(p.glob("*.air")) or sorted(p.rglob("*.air"))
            tests.extend(found)

    seen: set[Path] = set()
    tests = [t for t in tests if not (t in seen or seen.add(t))]

    if not tests:
        sys.exit(f"[ERROR] No .air projects found in: {args.target}")
        
    if args.shard_total > 1:
        tests = [t for i, t in enumerate(tests) if i % args.shard_total == args.shard_index]
        print(f"[INFO] Running shard {args.shard_index + 1}/{args.shard_total} ({len(tests)} tests)")

    # 4. Device Connection
    if args.device:
        uri = args.device if args.device.lower().startswith("android://") else f"Android://127.0.0.1:5037/{args.device}"
        connect_device(uri)
        device_id = args.device.rsplit("/", 1)[-1]
    else:
        init_device()
        device_id = G.DEVICE.serialno

    from pixon.common.adb_utils import set_default_serial
    set_default_serial(device_id)

    # 5. Output Configuration
    report_root = _dagster_dir / "report_run"
    report_root.mkdir(parents=True, exist_ok=True)
    scrcpy_path = str(_dagster_dir / "scrcpy-win64" / "scrcpy.exe")

    # 6. Execute Tests
    run_had_failure = False
    for air_path in tests:
        py_scripts = [p for p in air_path.glob("*.py") if p.name != "__init__.py"]
        if not py_scripts:
            print(f"[WARN] {air_path.name}: no .py script found, skipping", file=sys.stderr)
            continue
        failed = run_single_test(air_path, py_scripts[0], args.mode, device_id, report_root, scrcpy_path)
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
