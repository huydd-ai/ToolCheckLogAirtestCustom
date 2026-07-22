# Dynamic Benchmark System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded 12-metric benchmark evaluator with a config-driven engine whose metrics, categories, thresholds, and modes are all data-defined, rendered generically end-to-end.

**Architecture:** A JSON config file is the source of truth for categories/metrics/thresholds/modes. Compute logic lives in a code registry (`metric-id -> fn`); config selects and tunes it. The engine loads config, builds shared context once, runs each computor in config order, judges thresholds, and emits a generic payload. Missing input data yields N/A (never fabricated defaults). The dashboard loops over the payload so new config metrics appear automatically.

**Tech Stack:** Python 3.10+ (stdlib `json`, `statistics`), pytest, Alpine.js (existing dashboard).

## Global Constraints

- No new third-party dependency. Stdlib `json` only — no YAML. (verbatim: "no new third-party dependency (stdlib `json` only; no YAML)")
- No `eval` / formula-string config.
- No fabricated default values. Missing input → metric value `None` (N/A), excluded from pass/fail rollup, no action trigger.
- `evaluate_game_benchmarks` signature stays backward-compatible: `evaluate_game_benchmarks(runs, mode=None, config=None)`.
- Payload top-level keys unchanged: `mode`, `live_devices`, `categories`, `action_triggers`. `report_server.py` must need no edit.
- Default shipped config reproduces today's 12 metrics / 4 categories / same thresholds / `normal`+`aggressive` modes → zero behavior change except the four previously-faked metrics now show N/A.
- All internal imports package-qualified (`from dagster.reports.report_data import ...`).
- Run all commands from the project root `D:\AutoRebase` (parent of `dagster/`) so `dagster.*` and `pixon` resolve.

**Metric `direction` semantics (used throughout):** `min` → pass if `value >= threshold`; `max` → pass if `value <= threshold`; `eq` → pass if `value == threshold`. Trigger op glyph: `min`→`≥`, `max`→`≤`, `eq`→`=`.

**RunEntry fields available** (`dagster/reports/report_data.py`): `stem, when, status, folder, report_href, device, suite, duration, fps_avg, fps_min, ram_mb_peak, ram_mb_delta, scene_load_sec, asset_errors, chipset, net_profile`. Metrics `t_match_ms`, `r_cv_error_pct`, `t_input_latency_ms`, `c_critical_pct` have **no** backing field → their computors return `None` (N/A) until a probe adds fields.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `dagster/benchmark_config.json` | **new** — default 4-category / 12-metric config (data only). |
| `dagster/benchmark.py` | **modify** — add config loader + registry + computors; rewrite `evaluate_game_benchmarks`; generic `print_benchmark_table`; `--config`/`--mode` CLI. `compute_benchmarks` (per-stem runtime table) untouched. |
| `dagster/tests/test_benchmarks.py` | **modify** — rewrite the 4 `evaluate_game_benchmarks` tests to the new structure; keep `PerformanceProbe`/`DeviceManager` tests. |
| `dagster/static/index.html` | **modify** — replace 4 hardcoded metric cards with a generic category/metric loop. |
| `dagster/report_server.py` | **no change** (payload shape preserved). |

---

## Task 1: Config loader + registry infrastructure

**Files:**
- Modify: `dagster/benchmark.py` (add near top, after imports)
- Test: `dagster/tests/test_benchmarks.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `_METRICS: dict[str, Callable]`
  - `metric(name: str)` — decorator registering a computor under `name`.
  - `_resolve_config(config: dict | str | Path | None) -> dict` — returns a config dict. `None` → load+cache the default file `dagster/benchmark_config.json`; a `str`/`Path` → load that file; a `dict` → returned as-is.

- [ ] **Step 1: Write the failing test**

Add to `dagster/tests/test_benchmarks.py`:

```python
from dagster.benchmark import metric, _METRICS, _resolve_config


def test_metric_decorator_registers():
    @metric("unit_test_probe")
    def _probe(runs, ctx, results, params):
        return 1.0

    assert _METRICS["unit_test_probe"] is _probe
    assert _resolve_config(None)["modes"][0] == "normal"


def test_resolve_config_passthrough_dict():
    cfg = {"modes": ["x"], "categories": []}
    assert _resolve_config(cfg) is cfg
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `D:\AutoRebase`): `python -m pytest dagster/tests/test_benchmarks.py::test_metric_decorator_registers -v`
Expected: FAIL — `ImportError: cannot import name 'metric'`.

- [ ] **Step 3: Write minimal implementation**

In `dagster/benchmark.py`, after the existing imports (after line 13) add:

```python
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
```

- [ ] **Step 4: Create the default config file**

Create `dagster/benchmark_config.json`:

```json
{
  "modes": ["normal", "aggressive"],
  "categories": [
    {
      "id": "game_performance",
      "label": "Game Performance",
      "metrics": [
        {"id": "avg_fps", "label": "Avg FPS", "unit": "FPS", "compute": "avg_fps",
         "direction": "min", "thresholds": {"normal": 50.0, "aggressive": 55.0},
         "hard": 45.0, "trigger": "OPTIMIZE_GRAPHICS"},
        {"id": "combo_drop_fps", "label": "Combo FPS Drop", "unit": "FPS", "compute": "combo_drop_fps",
         "direction": "max", "thresholds": {"normal": 5.0, "aggressive": 3.0},
         "hard": 10.0, "trigger": "HALT_BUILD"},
        {"id": "r_leak_mb_hr", "label": "Memory Leak", "unit": "MB/hr", "compute": "r_leak",
         "direction": "max", "thresholds": {"normal": 15.0, "aggressive": 10.0},
         "trigger": "HALT_BUILD"},
        {"id": "a_fail_pct", "label": "Asset Load Failure", "unit": "%", "compute": "a_fail_pct",
         "direction": "eq", "thresholds": {"normal": 0.0, "aggressive": 0.0},
         "trigger": "HALT_BUILD"}
      ]
    },
    {
      "id": "emulator_stability",
      "label": "Emulator Stability",
      "metrics": [
        {"id": "r_crash_pct", "label": "Crash / ANR Rate", "unit": "%", "compute": "r_crash_pct",
         "direction": "max", "thresholds": {"normal": 0.5, "aggressive": 0.2},
         "trigger": "HALT_BUILD"},
        {"id": "r_softlock_pct", "label": "Automation Softlock", "unit": "%", "compute": "r_softlock_pct",
         "direction": "max", "thresholds": {"normal": 1.0, "aggressive": 0.5},
         "trigger": "REFACTOR_SCRIPTS"},
        {"id": "delta_ram_emu_mb_hr", "label": "Emulator RAM Leak", "unit": "MB/hr", "compute": "delta_ram_emu",
         "direction": "max", "thresholds": {"normal": 50.0, "aggressive": 30.0},
         "trigger": "RESTART_EMULATOR"},
        {"id": "e_scaling_pct", "label": "Multi-Instance Scaling", "unit": "%", "compute": "e_scaling",
         "direction": "min", "thresholds": {"normal": 85.0, "aggressive": 90.0},
         "trigger": "SCALE_INFRASTRUCTURE"}
      ]
    },
    {
      "id": "script_quality",
      "label": "Airtest Script Quality",
      "metrics": [
        {"id": "t_match_ms", "label": "Image Match Time", "unit": "ms", "compute": "probe_avg",
         "params": {"field": "cv_match_ms", "round": 1},
         "direction": "max", "thresholds": {"normal": 200.0, "aggressive": 150.0},
         "trigger": "OPTIMIZE_SCRIPT"},
        {"id": "r_cv_error_pct", "label": "CV Identification Error", "unit": "%", "compute": "probe_avg",
         "params": {"field": "cv_error_pct", "round": 2},
         "direction": "eq", "thresholds": {"normal": 0.0, "aggressive": 0.0},
         "trigger": "RECALIBRATE_CV"},
        {"id": "t_input_latency_ms", "label": "Input Latency", "unit": "ms", "compute": "probe_avg",
         "params": {"field": "input_latency_ms", "round": 1},
         "direction": "max", "thresholds": {"normal": 120.0, "aggressive": 80.0},
         "trigger": "OPTIMIZE_ADB"},
        {"id": "c_critical_pct", "label": "Critical Path Coverage", "unit": "%", "compute": "probe_avg",
         "params": {"field": "critical_path_pct", "round": 1},
         "direction": "eq", "thresholds": {"normal": 100.0, "aggressive": 100.0},
         "trigger": "AUDIT_COVERAGE"}
      ]
    },
    {
      "id": "infrastructure",
      "label": "Active Test Farm Hardware",
      "metrics": [
        {"id": "unique_devices", "label": "Active Devices", "unit": "", "compute": "unique_devices",
         "direction": "min", "thresholds": {"normal": 1, "aggressive": 1}},
        {"id": "unique_chipsets", "label": "Active Chipsets", "unit": "", "compute": "unique_chipsets",
         "direction": "min", "thresholds": {"normal": 1, "aggressive": 1}}
      ]
    }
  ]
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest dagster/tests/test_benchmarks.py::test_metric_decorator_registers dagster/tests/test_benchmarks.py::test_resolve_config_passthrough_dict -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add dagster/benchmark.py dagster/benchmark_config.json dagster/tests/test_benchmarks.py
git commit -m "feat(benchmark): add config loader, metric registry, default config"
```

---

## Task 2: Port computors into the registry

**Files:**
- Modify: `dagster/benchmark.py` (add computor fns using `@metric`)
- Test: `dagster/tests/test_benchmarks.py`

**Interfaces:**
- Consumes: `metric`, `_METRICS` (Task 1); `RunEntry`.
- Produces (all signature `fn(runs, ctx, results, params) -> float | int | None`, registered under the bracketed key):
  `avg_fps`, `combo_drop_fps`, `r_leak`, `a_fail_pct`, `r_crash_pct`, `r_softlock_pct`, `delta_ram_emu`, `e_scaling`, `unique_devices`, `unique_chipsets`, `probe_avg`, `constant`.
  `ctx` is a dict with keys: `total_runs, n_pass, n_fail, duration_hours, live_devices, live_device_serials, live_chipsets, run_devices, run_chipsets, by_stem`.
  `results` is `dict[metric_id, value]` filled in config order (so `delta_ram_emu` can read `results["r_leak_mb_hr"]`).

- [ ] **Step 1: Write the failing tests**

Add to `dagster/tests/test_benchmarks.py`:

```python
from datetime import datetime as _dt


def _ctx(runs):
    # minimal ctx builder mirroring engine (Task 3 builds the real one)
    from dagster.benchmark import _build_ctx
    return _build_ctx(runs)


def test_computor_avg_fps_and_na():
    now = _dt.now()
    r_ok = RunEntry(stem="a", when=now, status="PASS", folder="a", report_href="h",
                    device="d1", suite="S", duration=10.0, fps_avg=58.0, fps_min=55.0,
                    ram_mb_delta=1.0, asset_errors=0, chipset="C")
    r_nofps = RunEntry(stem="b", when=now, status="PASS", folder="b", report_href="h",
                       device="d1", suite="S", duration=10.0, fps_avg=None, fps_min=None,
                       ram_mb_delta=1.0, asset_errors=0, chipset="C")
    assert _METRICS["avg_fps"]([r_ok], _ctx([r_ok]), {}, {}) == 58.0
    assert _METRICS["avg_fps"]([r_nofps], _ctx([r_nofps]), {}, {}) is None


def test_computor_delta_ram_reads_results():
    results = {"r_leak_mb_hr": 10.0}
    assert _METRICS["delta_ram_emu"]([], {}, results, {}) == 18.0
    assert _METRICS["delta_ram_emu"]([], {}, {"r_leak_mb_hr": None}, {}) is None


def test_computor_probe_avg_na_when_field_absent():
    now = _dt.now()
    r = RunEntry(stem="a", when=now, status="PASS", folder="a", report_href="h",
                 device="d1", suite="S", duration=10.0, fps_avg=58.0, fps_min=55.0,
                 ram_mb_delta=1.0, asset_errors=0, chipset="C")
    # cv_match_ms not a RunEntry field -> N/A
    assert _METRICS["probe_avg"]([r], _ctx([r]), {}, {"field": "cv_match_ms", "round": 1}) is None


def test_computor_constant():
    assert _METRICS["constant"]([], {}, {}, {"value": 42.0}) == 42.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest dagster/tests/test_benchmarks.py -k "computor" -v`
Expected: FAIL — `KeyError: 'avg_fps'` / `ImportError: _build_ctx`.

- [ ] **Step 3: Write the ctx builder and computors**

In `dagster/benchmark.py`, add after the registry infra:

```python
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
```

Note: `delta_ram_emu` reads `results["r_leak_mb_hr"]` — the config metric **id** for the leak metric is `r_leak_mb_hr` (compute key `r_leak`). Results are keyed by metric **id**.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest dagster/tests/test_benchmarks.py -k "computor" -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add dagster/benchmark.py dagster/tests/test_benchmarks.py
git commit -m "feat(benchmark): port 12 computors + ctx builder into registry"
```

---

## Task 3: Rewrite the engine (`evaluate_game_benchmarks`)

**Files:**
- Modify: `dagster/benchmark.py` (replace body of `evaluate_game_benchmarks`, lines 98-338)
- Test: `dagster/tests/test_benchmarks.py`

**Interfaces:**
- Consumes: `_resolve_config`, `_build_ctx`, `_METRICS` (Tasks 1-2).
- Produces: `evaluate_game_benchmarks(runs, mode=None, config=None) -> dict` with payload shape from the spec (`mode`, `live_devices`, `categories` keyed by id each with `label`/`status`/`metrics[]`, `action_triggers`). Helper `_judge(value, direction, threshold, hard) -> tuple[bool | None, str | None]` returns `(passed, severity)` where severity ∈ `{None, "WARN", "FAIL"}`.

- [ ] **Step 1: Write the failing tests**

Replace the four old `evaluate_game_benchmarks` tests (`test_evaluate_game_benchmarks_pass`, `test_all_12_puzzle_game_benchmark_formulas`, `test_evaluate_game_benchmarks_action_triggers`, `test_evaluate_game_benchmarks_aggressive_mode`) with:

```python
def _run(stem, status, fps_avg, fps_min, ram_delta, asset_errors=0, dur=10.0, chip="Snap"):
    return RunEntry(stem=stem, when=datetime.now(), status=status,
                    folder=stem, report_href="h", device="d1", suite="S",
                    duration=dur, fps_avg=fps_avg, fps_min=fps_min,
                    ram_mb_peak=500.0, ram_mb_delta=ram_delta,
                    asset_errors=asset_errors, chipset=chip)


def _find_metric(res, cat_id, metric_id):
    for m in res["categories"][cat_id]["metrics"]:
        if m["id"] == metric_id:
            return m
    raise AssertionError(f"{metric_id} not in {cat_id}")


def test_engine_default_shape_and_pass():
    runs = [_run("tc01", "PASS", 58.0, 55.0, 1.0), _run("tc02", "PASS", 59.0, 56.0, 2.0)]
    res = evaluate_game_benchmarks(runs)
    assert res["mode"] == "normal"
    assert set(res["categories"]) == {
        "game_performance", "emulator_stability", "script_quality", "infrastructure"}
    gp = _find_metric(res, "game_performance", "avg_fps")
    assert gp["value"] == 58.5 and gp["passed"] is True and gp["unit"] == "FPS"
    assert res["categories"]["game_performance"]["status"] == "PASS"


def test_engine_na_metric_excluded_from_rollup():
    runs = [_run("tc01", "PASS", 58.0, 55.0, 1.0)]
    res = evaluate_game_benchmarks(runs)
    tm = _find_metric(res, "script_quality", "t_match_ms")
    assert tm["value"] is None and tm["passed"] is None       # N/A, no backing field
    # script_quality is all-N/A -> category status "N/A", not FAIL
    assert res["categories"]["script_quality"]["status"] == "N/A"


def test_engine_breach_emits_trigger_and_hard_fail():
    runs = [_run("tc01", "FAIL", 40.0, 40.0, 1.0)]   # avg_fps 40 < hard 45 -> FAIL
    res = evaluate_game_benchmarks(runs)
    avg = _find_metric(res, "game_performance", "avg_fps")
    assert avg["passed"] is False
    assert res["categories"]["game_performance"]["status"] == "FAIL"
    assert any("OPTIMIZE_GRAPHICS" in t for t in res["action_triggers"])


def test_engine_mode_switch_and_prefix():
    runs = [_run("tc01", "PASS", 52.0, 50.0, 0.0)]   # 52 passes normal(50), fails aggressive(55)
    assert evaluate_game_benchmarks(runs, mode="normal")["categories"]["game_performance"]["status"] == "PASS"
    aggr = evaluate_game_benchmarks(runs, mode="aggressive")
    assert aggr["mode"] == "aggressive"
    assert any("[AGGRESSIVE]" in t and "OPTIMIZE_GRAPHICS" in t for t in aggr["action_triggers"])


def test_engine_arbitrary_config_and_constant():
    cfg = {
        "modes": ["ci"],
        "categories": [{
            "id": "custom", "label": "Custom", "metrics": [
                {"id": "fixed", "label": "Fixed Target", "unit": "x", "compute": "constant",
                 "params": {"value": 7.0}, "direction": "min",
                 "thresholds": {"ci": 5.0}, "trigger": "CHECK"}
            ]}]}
    res = evaluate_game_benchmarks([], config=cfg)
    assert res["mode"] == "ci"
    m = _find_metric(res, "custom", "fixed")
    assert m["value"] == 7.0 and m["passed"] is True
    assert res["action_triggers"] == []


def test_engine_bad_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        evaluate_game_benchmarks([], mode="nope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest dagster/tests/test_benchmarks.py -k "engine" -v`
Expected: FAIL — old engine returns the old shape (KeyError on `metrics` list / `set(categories)` mismatch).

- [ ] **Step 3: Rewrite the engine**

In `dagster/benchmark.py`, replace the entire `evaluate_game_benchmarks` function (current lines 98-338) with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest dagster/tests/test_benchmarks.py -k "engine or computor or metric or resolve" -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add dagster/benchmark.py dagster/tests/test_benchmarks.py
git commit -m "feat(benchmark): config-driven engine with N/A handling and dynamic modes"
```

---

## Task 4: Generic CLI table + `--config`/`--mode`

**Files:**
- Modify: `dagster/benchmark.py` (`print_benchmark_table` game section + `main`)
- Test: `dagster/tests/test_benchmarks.py`

**Interfaces:**
- Consumes: `evaluate_game_benchmarks` payload (Task 3).
- Produces: `print_benchmark_table(benchmarks, game_benchmarks=None)` iterating `categories`/`metrics` generically, printing `N/A` for `value is None`. `main` accepts `--config` and `--mode`.

- [ ] **Step 1: Write the failing test**

Add to `dagster/tests/test_benchmarks.py`:

```python
def test_print_table_generic_na(capsys):
    from dagster.benchmark import print_benchmark_table
    runs = [_run("tc01", "PASS", 58.0, 55.0, 1.0)]
    gb = evaluate_game_benchmarks(runs)
    print_benchmark_table({}, gb)
    out = capsys.readouterr().out
    assert "Game Performance" in out
    assert "Avg FPS" in out
    assert "N/A" in out   # script_quality metrics render N/A
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest dagster/tests/test_benchmarks.py::test_print_table_generic_na -v`
Expected: FAIL — old print iterates `cat_data` as a flat dict, prints raw repr, no "Game Performance" label / no "N/A".

- [ ] **Step 3: Rewrite the game section of `print_benchmark_table`**

In `dagster/benchmark.py`, replace the `if game_benchmarks:` block inside `print_benchmark_table` (current lines 372-384) with:

```python
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
```

- [ ] **Step 4: Add `--config`/`--mode` to `main`**

In `dagster/benchmark.py::main`, add after the `--suite` argument:

```python
    parser.add_argument("--config", type=str, default=None,
                        help="Path to benchmark config JSON (default: benchmark_config.json).")
    parser.add_argument("--mode", type=str, default=None,
                        help="Threshold mode/profile name (default: first configured mode).")
```

And change the `evaluate_game_benchmarks(runs)` call to:

```python
    game_benchmarks = evaluate_game_benchmarks(runs, mode=args.mode, config=args.config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest dagster/tests/test_benchmarks.py::test_print_table_generic_na -v`
Expected: PASS.

- [ ] **Step 6: Full suite + CLI smoke**

Run: `python -m pytest dagster/tests/test_benchmarks.py -v`
Expected: all passed.

Run: `python dagster/benchmark.py --mode aggressive` (from `D:\AutoRebase`)
Expected: runs without error; prints the matrix with the `(aggressive)` header (or "No runs found." if `report_run/` empty — both acceptable).

- [ ] **Step 7: Commit**

```bash
git add dagster/benchmark.py dagster/tests/test_benchmarks.py
git commit -m "feat(benchmark): generic CLI table + --config/--mode flags"
```

---

## Task 5: Generic dashboard rendering

**Files:**
- Modify: `dagster/static/index.html` (benchmark matrix section, current lines ~300-460)

**Interfaces:**
- Consumes: `game_benchmarks` payload (Task 3) via existing `gameBenchmarks` Alpine state.
- Produces: no JS API change; DOM now loops categories/metrics.

**Note:** No unit test (Alpine template). Verified via the browser preview per the steps below.

- [ ] **Step 1: Locate the benchmark matrix markup**

Open `dagster/static/index.html`. Find the two regions:
- The "highlight" strip using `gameBenchmarks?.categories?.game_performance?.avg_fps` etc. (current ~lines 310-370).
- The `bench-matrix-grid` block with four hardcoded `bench-card` divs (current ~lines 401-460).

- [ ] **Step 2: Replace the hardcoded highlight strip**

Delete the hardcoded per-metric highlight blocks (the `avg_fps`/`combo_drop_fps`/`r_leak_mb_hr`/`t_match_ms` strip, current ~lines 310-370). The generic grid below replaces their purpose. (If a hero/summary line is desired, keep only a static heading — do not reference specific metric ids.)

- [ ] **Step 3: Replace the `bench-matrix-grid` with a generic loop**

Replace the four hardcoded `bench-card` divs inside `bench-matrix-grid` with:

```html
<div class="bench-matrix-grid" x-show="gameBenchmarks?.categories">
  <template x-for="(cat, cid) in gameBenchmarks.categories" :key="cid">
    <div class="bench-card glass-panel" :class="cat.status.toLowerCase()">
      <div class="bench-card-header">
        <h3 x-text="cat.label"></h3>
        <span class="status-pill" :class="cat.status.toLowerCase()" x-text="cat.status"></span>
      </div>
      <div class="bench-card-metrics">
        <template x-for="m in cat.metrics" :key="m.id">
          <div class="bench-metric-row">
            <span class="bench-metric-label" x-text="m.label"></span>
            <strong class="bench-metric-value"
                    x-text="m.value === null ? 'N/A' : (m.value + (m.unit ? ' ' + m.unit : ''))"></strong>
            <span class="bench-metric-flag"
                  x-text="m.passed === null ? '—' : (m.passed ? 'PASS' : 'BREACH')"
                  :style="`color: ${m.passed === null ? 'var(--muted)' : (m.passed ? 'var(--pass)' : 'var(--warn)')}`"></span>
            <small class="bench-metric-thr" x-show="m.threshold !== null"
                   x-text="`${m.direction === 'min' ? '≥' : m.direction === 'max' ? '≤' : '='} ${m.threshold}${m.unit ? ' ' + m.unit : ''}`"></small>
          </div>
        </template>
      </div>
    </div>
  </template>
</div>
```

Leave the `action-triggers-banner` block (current ~lines 463-469) unchanged — it already loops `gameBenchmarks?.action_triggers` generically.

- [ ] **Step 4: Add minimal CSS for the new rows**

If `.bench-metric-row` has no style, append to the `<style>` block (or `static/styles.css` if that's where bench styles live — check first):

```css
.bench-metric-row { display: flex; align-items: baseline; gap: 8px; justify-content: space-between; padding: 2px 0; }
.bench-metric-label { flex: 1; }
.bench-metric-thr { opacity: 0.6; }
```

- [ ] **Step 5: Verify in the browser preview**

Start the dashboard and confirm generic rendering:

1. `preview_start` with `{name: "dashboard"}` if `.claude/launch.json` has it; else `preview_start` `{url: "http://localhost:7070"}` after starting `python dagster/report_server.py --port 7070`.
2. Navigate to the benchmarks view.
3. `read_page` — confirm four category cards render with their labels, and script-quality metrics show `N/A`.
4. `read_console_messages` — confirm no Alpine errors.
5. `computer {action: "screenshot"}` — capture proof.

Expected: four cards (`Game Performance`, `Emulator Stability`, `Airtest Script Quality`, `Active Test Farm Hardware`), N/A on the un-probed metrics, no console errors.

- [ ] **Step 6: Commit**

```bash
git add dagster/static/index.html dagster/static/styles.css
git commit -m "feat(dashboard): render benchmark categories/metrics generically"
```

---

## Task 6: Full regression + docs sync

**Files:**
- Modify: `dagster/CLAUDE.md` (benchmark note, if present) — optional
- Verify only: whole suite

- [ ] **Step 1: Run the full dagster test suite**

Run (from `D:\AutoRebase`): `python -m pytest dagster/tests/ -v`
Expected: all passed (benchmark + report_data + ldplayer + report_server + probe + device tests).

- [ ] **Step 2: Confirm `report_server.py` still serves benchmarks unchanged**

Run: `python dagster/report_server.py --port 7071` then in the browser preview navigate to `http://localhost:7071/api/benchmarks?mode=aggressive`.
Expected: 200 JSON with `game_benchmarks.categories` (keyed by id, each with `metrics[]`), `mode: "aggressive"`, `action_triggers` array. No traceback in `preview_logs`.

- [ ] **Step 3: Update `graphify` map**

Run: `graphify update dagster` (AST-only, no API cost) to keep the graph current after the refactor.

- [ ] **Step 4: Commit any doc/graph changes**

```bash
git add -A
git commit -m "chore(benchmark): regression pass + graph update for dynamic benchmark system"
```

---

## Self-Review

**Spec coverage:**
- Config file JSON + CLI override → Task 1 (config) + Task 4 (`--config`/`--mode`). ✔
- Registry compute model → Task 2. ✔
- Arbitrary named modes → Task 3 (`modes` from config, `mode` validated) + `test_engine_arbitrary_config_and_constant`. ✔
- No fabricated defaults / N/A → Tasks 2-3, `test_engine_na_metric_excluded_from_rollup`. ✔
- Dashboard generic end-to-end → Task 5. ✔
- Default config = today's 12 metrics / zero behavior change → Task 1 config content; four faked metrics → N/A via `probe_avg` on absent fields. ✔
- Payload top-level shape preserved / `report_server.py` untouched → Task 3 return + Task 6 Step 2 verify. ✔
- Error handling (bad mode, unknown compute, missing threshold, computor exception) → Task 3 engine (`ValueError`, `KeyError`, threshold-None path, try/except). ✔

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✔

**Type consistency:** `_build_ctx` keys used identically across Tasks 2-3; `results` keyed by metric **id** (`r_leak_mb_hr`) consumed by `delta_ram_emu` — matches config id. `_judge` returns `(passed, severity)` used consistently. `_OP` defined in Task 3, reused in Task 4 print. Payload metric dict keys (`id,label,value,unit,threshold,direction,passed`) identical in engine, tests, CLI, and dashboard. ✔
