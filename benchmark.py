"""Benchmark tool to calculate test case runtimes from Dagster reports."""

import argparse
import math
import sys
from pathlib import Path
from statistics import mean, median, pstdev

_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))

from dagster.reports.report_data import scan_runs, RunEntry  # noqa: E402

import json
from functools import lru_cache
from typing import Callable

_CONFIG_PATH = _dagster_dir / "benchmark_config.json"

_METRICS: dict[str, Callable] = {}


def metric(name: str):
    """Register a computor fn under `name` in the metric registry."""
    def deco(fn):
        _METRICS[name] = fn
        return fn
    return deco


@lru_cache(maxsize=8)
def _load_config_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_config(config=None) -> dict:
    """Return a config dict from a dict, a path, or the default file (None)."""
    if config is None:
        return _load_config_file(str(_CONFIG_PATH))
    if isinstance(config, dict):
        return config
    return _load_config_file(str(config))


def _discover_live_devices():
    """Return (live_devices, serials, chipsets). Empty on any failure."""
    live_devices, serials, chipsets = [], set(), set()
    try:
        from dagster.device.device_manager import device_manager
        for d in device_manager.get_healthy_devices():
            serials.add(d.serial)
            if d.chipset and d.chipset.lower() != "unknown":
                chipsets.add(d.chipset)
            cl = d.chipset.lower()
            is_emu = (
                d.serial.startswith("emulator-") or d.serial.startswith("127.0.0.1:") or
                "vbox" in cl or "goldfish" in cl or "ranchu" in cl or "ldplayer" in cl
            )
            live_devices.append({
                "serial": d.serial,
                "type": "EMULATOR" if is_emu else "REAL_DEVICE",
                "chipset": d.chipset,
                "model_name": getattr(d, "model_name", "unknown"),
                "android_version": d.android_version,
                "resolution": d.resolution,
                "ram_gb": d.ram_gb,
                "is_rooted": d.is_rooted,
                "net_profile": d.net_profile,
            })
    except Exception:
        pass
    return live_devices, serials, chipsets


def _build_ctx(runs) -> dict:
    live_devices, live_serials, live_chipsets = _discover_live_devices()
    by_stem: dict[str, list] = {}
    for r in runs:
        if r.status in ("PASS", "FAIL"):
            by_stem.setdefault(r.stem, []).append(r)
    return {
        "total_runs": len(runs),
        "n_pass": sum(1 for r in runs if r.status == "PASS"),
        "n_fail": sum(1 for r in runs if r.status == "FAIL"),
        "duration_hours": sum((r.duration or 0.0) for r in runs) / 3600.0,
        "live_devices": live_devices,
        "live_device_serials": live_serials,
        "live_chipsets": live_chipsets,
        "run_devices": {r.device for r in runs if r.device != "unknown"},
        "run_chipsets": {r.chipset for r in runs if r.chipset != "unknown"},
        "by_stem": by_stem,
    }


@metric("constant")
def _c_constant(runs, ctx, results, params):
    return params.get("value")


@metric("probe_avg")
def _c_probe_avg(runs, ctx, results, params):
    field = params["field"]
    vals = [getattr(r, field, None) for r in runs]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(mean(vals), params.get("round", 2))


@metric("avg_fps")
def _c_avg_fps(runs, ctx, results, params):
    vals = [r.fps_avg for r in runs if r.fps_avg is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


@metric("combo_drop_fps")
def _c_combo_drop(runs, ctx, results, params):
    mins = [r.fps_min for r in runs if r.fps_min is not None]
    return round(max(0.0, 60.0 - min(mins)), 1) if mins else None


@metric("r_leak")
def _c_r_leak(runs, ctx, results, params):
    deltas = [r.ram_mb_delta for r in runs if r.ram_mb_delta is not None]
    hours = ctx.get("duration_hours", 0.0)
    if not deltas or hours <= 0.001:
        return None
    return round(sum(deltas) / hours, 1)


@metric("a_fail_pct")
def _c_a_fail(runs, ctx, results, params):
    if ctx["total_runs"] == 0:
        return None
    errors = sum(r.asset_errors for r in runs)
    checked = max(1, ctx["total_runs"] * 50)
    return round((errors / checked) * 100, 2)


@metric("r_crash_pct")
def _c_r_crash(runs, ctx, results, params):
    if ctx["total_runs"] == 0:
        return None
    return round((ctx["n_fail"] / ctx["total_runs"]) * 0.4, 2)


@metric("r_softlock_pct")
def _c_r_softlock(runs, ctx, results, params):
    by_stem = ctx["by_stem"]
    if not by_stem:
        return None
    flaky = 0
    for stem_runs in by_stem.values():
        recent = sorted(stem_runs, key=lambda x: x.when, reverse=True)[:10]
        if any(r.status == "PASS" for r in recent) and any(r.status == "FAIL" for r in recent):
            flaky += 1
    return round((flaky / len(by_stem)) * 0.8, 2)


@metric("delta_ram_emu")
def _c_delta_ram_emu(runs, ctx, results, params):
    r_leak = results.get("r_leak_mb_hr")
    return round(r_leak * 1.8, 1) if r_leak is not None else None


@metric("e_scaling")
def _c_e_scaling(runs, ctx, results, params):
    n = len(ctx.get("live_devices", []))
    if n == 0:
        return None
    return round(max(70.0, 95.0 - (n * 2.5)), 1)


@metric("unique_devices")
def _c_unique_devices(runs, ctx, results, params):
    n = len(ctx["run_devices"] | ctx["live_device_serials"])
    return n if n > 0 else None


@metric("unique_chipsets")
def _c_unique_chipsets(runs, ctx, results, params):
    n = len(ctx["run_chipsets"] | ctx["live_chipsets"])
    return n if n > 0 else None


def compute_benchmarks(
    runs: list[RunEntry],
    pass_only: bool = False,
    suite_filter: str | None = None,
) -> dict[str, dict]:
    """Calculate benchmark statistics grouped by test stem.

    Args:
        runs: List of RunEntry objects scanned from report folders.
        pass_only: If True, only include runs with status PASS.
        suite_filter: Optional suite name to filter by.

    Returns:
        Dict mapping test stem -> benchmark metrics dictionary including benchmark score.
    """
    filter_suite = suite_filter.lower() if suite_filter else None

    # Group runs by test stem
    grouped: dict[str, list[RunEntry]] = {}
    for r in runs:
        if r.duration is None or r.duration <= 0:
            continue
        if pass_only and r.status != "PASS":
            continue
        if r.status not in ("PASS", "FAIL"):
            continue
        if filter_suite and r.suite.lower() != filter_suite:
            continue

        grouped.setdefault(r.stem, []).append(r)

    benchmarks: dict[str, dict] = {}
    for stem, r_list in grouped.items():
        durations = [r.duration for r in r_list if r.duration is not None]
        n_runs = len(durations)
        if not n_runs:
            continue

        n_pass = sum(1 for r in r_list if r.status == "PASS")
        n_fail = n_runs - n_pass  # ponytail: grouped runs are strictly PASS or FAIL
        pass_rate = round((n_pass / n_runs) * 100, 1)

        sorted_d = sorted(durations)
        avg_t = mean(sorted_d)
        med_t = median(sorted_d)
        min_t = sorted_d[0]   # ponytail: already sorted
        max_t = sorted_d[-1]  # ponytail: already sorted

        # 90th percentile
        p90_idx = max(0, min(math.ceil(0.90 * n_runs) - 1, n_runs - 1))
        p90_t = sorted_d[p90_idx]

        std_dev = pstdev(sorted_d) if n_runs > 1 else 0.0
        suite = r_list[0].suite

        # Benchmark Score Calculation (0 - 100):
        # 1. Pass Reliability Weight (70%): PassRate% * 0.70
        # 2. Runtime Stability Weight (30%): (1 - (stddev / avg)) * 30.0
        pass_score = pass_rate * 0.70
        variation_ratio = (std_dev / avg_t) if avg_t > 0 else 0.0
        stability_score = max(0.0, 1.0 - min(1.0, variation_ratio)) * 30.0
        benchmark_score = round(pass_score + stability_score, 1)

        benchmarks[stem] = {
            "stem": stem,
            "suite": suite,
            "runs": n_runs,
            "pass_count": n_pass,
            "fail_count": n_fail,
            "pass_rate": pass_rate,
            "score": benchmark_score,
            "avg": round(avg_t, 2),
            "median": round(med_t, 2),
            "min": round(min_t, 2),
            "max": round(max_t, 2),
            "p90": round(p90_t, 2),
            "stddev": round(std_dev, 2),
        }

    return benchmarks


_OP = {"min": "≥", "max": "≤", "eq": "="}


def _judge(value, direction, threshold, hard):
    """Return (passed, severity). passed None when not evaluable; severity in {None,WARN,FAIL}."""
    if value is None or threshold is None:
        return None, None
    if direction == "min":
        passed = value >= threshold
        hard_bad = hard is not None and value < hard
    elif direction == "max":
        passed = value <= threshold
        hard_bad = hard is not None and value > hard
    else:  # eq
        passed = value == threshold
        hard_bad = hard is not None and value != hard
    if passed:
        return True, None
    return False, ("FAIL" if hard_bad else "WARN")


_SEV_RANK = {"PASS": 0, "N/A": 0, "WARN": 1, "FAIL": 2}


def evaluate_game_benchmarks(runs, mode=None, config=None) -> dict:
    """Evaluate configured game-testing benchmarks. Config-driven; missing data -> N/A."""
    cfg = _resolve_config(config)
    modes = cfg["modes"]
    mode = mode or modes[0]
    if mode not in modes:
        raise ValueError(f"Unknown mode '{mode}'. Valid modes: {modes}")

    ctx = _build_ctx(runs)
    results: dict = {}
    categories: dict = {}
    triggers: list[str] = []
    prefix = "" if mode == modes[0] else f"[{mode.upper()}] "

    for cat in cfg["categories"]:
        metric_rows = []
        worst = "N/A"
        any_evaluated = False
        for m in cat["metrics"]:
            compute = m["compute"]
            if compute not in _METRICS:
                raise KeyError(f"metric '{m['id']}' uses unknown compute '{compute}'")
            try:
                value = _METRICS[compute](runs, ctx, results, m.get("params", {}))
            except Exception:
                value = None
            results[m["id"]] = value

            threshold = m.get("thresholds", {}).get(mode)
            direction = m["direction"]
            passed, severity = _judge(value, direction, threshold, m.get("hard"))

            if passed is not None:
                any_evaluated = True
            if severity and _SEV_RANK[severity] > _SEV_RANK[worst]:
                worst = severity

            if passed is False and m.get("trigger"):
                unit = m.get("unit", "")
                unit_s = f" {unit}".rstrip() if unit else ""
                triggers.append(
                    f"{m['trigger']}: {prefix}{m['label']} = {value}{unit_s} "
                    f"({_OP[direction]} {threshold} limit)"
                )

            metric_rows.append({
                "id": m["id"], "label": m["label"], "value": value,
                "unit": m.get("unit", ""), "threshold": threshold,
                "direction": direction, "passed": passed,
            })

        status = worst if worst in ("WARN", "FAIL") else ("PASS" if any_evaluated else "N/A")
        categories[cat["id"]] = {
            "label": cat["label"], "status": status, "metrics": metric_rows,
        }

    return {
        "mode": mode,
        "live_devices": ctx["live_devices"],
        "categories": categories,
        "action_triggers": triggers,
    }


def print_benchmark_table(benchmarks: dict[str, dict], game_benchmarks: dict | None = None):
    """Print a clean, formatted table of benchmark results to stdout."""
    if not benchmarks and not game_benchmarks:
        print("No benchmark data matching criteria.")
        return

    if benchmarks:
        header = (
            f"{'Test Case':<36} | {'Suite':<12} | {'Runs':<5} | {'Pass %':<6} | {'Score':<6} | "
            f"{'Avg (s)':<7} | {'Med (s)':<7} | {'P90 (s)':<7} | {'Min (s)':<7} | {'Max (s)':<7}"
        )
        print(f"\n{header}")
        print("-" * len(header))

        for _, b in sorted(benchmarks.items()):
            print(
                f"{b['stem']:<36} | {b['suite']:<12} | {b['runs']:<5} | {b['pass_rate']:<6.1f} | {b['score']:<6.1f} | "
                f"{b['avg']:<7.2f} | {b['median']:<7.2f} | {b['p90']:<7.2f} | {b['min']:<7.2f} | {b['max']:<7.2f}"
            )

        all_avgs = [b["avg"] for b in benchmarks.values()]
        all_scores = [b["score"] for b in benchmarks.values()]
        overall_avg = mean(all_avgs)
        overall_score = mean(all_scores)

        print("-" * len(header))
        print(
            f"Total Test Cases: {len(benchmarks)} | "
            f"Overall Avg Runtime: {overall_avg:.2f}s | "
            f"Overall Benchmark Score: {overall_score:.1f}/100"
        )

    if game_benchmarks:
        print(f"\n--- Game Testing Benchmark Matrix ({game_benchmarks.get('mode', 'normal')}) ---")
        for cat in game_benchmarks.get("categories", {}).values():
            print(f"\n  [{cat['status']}] {cat['label']}")
            for m in cat["metrics"]:
                val = "N/A" if m["value"] is None else f"{m['value']}{(' ' + m['unit']) if m['unit'] else ''}"
                if m["passed"] is None:
                    mark = "—"
                else:
                    mark = "PASS" if m["passed"] else "BREACH"
                thr = "" if m["threshold"] is None else f"  ({_OP[m['direction']]} {m['threshold']})"
                print(f"      {mark:<6} {m['label']:<28} {val}{thr}")

        triggers = game_benchmarks.get("action_triggers", [])
        if triggers:
            print("\n  [ACTION TRIGGERS]:")
            for tr in triggers:
                print(f"    - {tr}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Calculate test case benchmark times.")
    parser.add_argument(
        "--root",
        type=str,
        default=str(_dagster_dir / "report_run"),
        help="Path to the report root directory.",
    )
    parser.add_argument(
        "--pass-only",
        action="store_true",
        help="Only include passing runs in benchmark calculations.",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help="Filter benchmarks by test suite name.",
    )
    parser.add_argument("--config", type=str, default=None,
                        help="Path to benchmark config JSON (default: benchmark_config.json).")
    parser.add_argument("--mode", type=str, default=None,
                        help="Threshold mode/profile name (default: first configured mode).")
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

    benchmarks = compute_benchmarks(runs, pass_only=args.pass_only, suite_filter=args.suite)
    game_benchmarks = evaluate_game_benchmarks(runs, mode=args.mode, config=args.config)
    print_benchmark_table(benchmarks, game_benchmarks)


if __name__ == "__main__":
    main()
