"""Benchmark tool to calculate test case runtimes from Dagster reports."""

import argparse
import sys
from pathlib import Path
from statistics import mean, median

_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))

from dagster.reports.report_data import scan_runs

def main():
    parser = argparse.ArgumentParser(description="Calculate test case benchmark times.")
    parser.add_argument("--root", type=str, default=str(_dagster_dir / "report_run"),
                        help="Path to the report root directory.")
    args = parser.parse_args()

    report_root = Path(args.root).resolve()
    if not report_root.exists():
        print(f"Report root not found: {report_root}")
        sys.exit(1)

    print(f"Scanning runs in {report_root}...")
    runs = scan_runs(report_root)
    
    if not runs:
        print("No runs found.")
        return

    # Group durations by test stem (only consider PASS/FAIL for accurate benchmarking)
    benchmarks = {}
    for r in runs:
        if r.duration is not None and r.duration > 0 and r.status in ("PASS", "FAIL"):
            if r.stem not in benchmarks:
                benchmarks[r.stem] = []
            benchmarks[r.stem].append(r.duration)

    if not benchmarks:
        print("No duration data found in runs.")
        return

    print(f"\n{'Test Case':<40} | {'Runs':<6} | {'Avg (s)':<8} | {'Median':<8} | {'Min (s)':<8} | {'Max (s)':<8}")
    print("-" * 90)

    # Sort alphabetically
    for stem in sorted(benchmarks.keys()):
        durations = benchmarks[stem]
        n_runs = len(durations)
        avg_t = mean(durations)
        med_t = median(durations)
        min_t = min(durations)
        max_t = max(durations)
        
        print(f"{stem:<40} | {n_runs:<6} | {avg_t:<8.2f} | {med_t:<8.2f} | {min_t:<8.2f} | {max_t:<8.2f}")

    print("\nBenchmark calculation complete.")

if __name__ == "__main__":
    main()
