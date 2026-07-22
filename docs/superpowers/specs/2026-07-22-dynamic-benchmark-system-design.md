# Dynamic Benchmark System — Design

**Date:** 2026-07-22
**Status:** Approved (design), pending implementation plan

## Problem

`dagster/benchmark.py::evaluate_game_benchmarks` hardcodes everything: 12 metrics
across 4 categories, per-mode thresholds baked into Python, exactly 2 modes
(`normal`/`aggressive`), and inline action-trigger strings. The dashboard
(`static/index.html`) and `tests/test_benchmarks.py` are coupled to the exact
category keys, metric field names, and display thresholds. Adding, removing, or
retuning a metric requires editing code in three places.

Additionally the current code **fabricates default values** when data is absent
(`avg_fps=58.5`, `r_leak=2.5`, `t_match_ms=145`, etc.), presenting un-measured
placeholders as real measurements.

## Goals

1. Metric set, categories, thresholds, and modes are **data-driven** (config
   file), not hardcoded. The **number** of metrics/categories/modes is arbitrary.
2. Compute logic lives in a **code registry**; config selects and tunes it.
   Adding a metric that reuses an existing computor or a constant target = config
   edit only. A genuinely new formula = one new registry function.
3. Thresholds default from config, **overridable per run via CLI**.
4. Arbitrary named **mode profiles** (not just normal/aggressive).
5. **No fabricated defaults.** Missing input data → metric value is **N/A**
   (`null`), excluded from pass/fail rollup, no action trigger.
6. Dashboard renders **generically** end-to-end — a metric added in config shows
   up as a card row automatically.
7. Default shipped config reproduces today's 12 metrics / 4 categories exactly →
   **zero behavior change** out of the box (except previously-faked metrics now
   correctly show N/A until a probe feeds them).

## Non-goals

- No formula-string / `eval` config (rejected: bug/security farm).
- No auto-derived thresholds from historical data.
- No changes to `report_data.py` scanning or the `PerformanceProbe`.
- No new third-party dependency (stdlib `json` only; no YAML).

## Architecture

Four units, each independently testable:

1. **Config** (`benchmark_config.json`) — data-only source of truth.
2. **Registry** (`benchmark.py`) — `metric-id → compute fn`.
3. **Engine** (`benchmark.py::evaluate_game_benchmarks`) — loads config, builds
   shared context, runs computors, judges thresholds, emits payload.
4. **Consumers** — CLI table (`benchmark.py::main`/`print_benchmark_table`),
   dashboard (`static/index.html`), `report_server.py` (unchanged — payload
   top-level shape preserved).

### 1. Config schema — `dagster/benchmark_config.json`

```json
{
  "modes": ["normal", "aggressive"],
  "categories": [
    {
      "id": "game_performance",
      "label": "Game Performance",
      "metrics": [
        {
          "id": "avg_fps",
          "label": "Avg FPS",
          "unit": "FPS",
          "compute": "avg_fps",
          "direction": "min",
          "thresholds": {"normal": 50.0, "aggressive": 55.0},
          "hard": 45.0,
          "trigger": "OPTIMIZE_GRAPHICS"
        }
      ]
    }
  ]
}
```

Field semantics:

| Field | Meaning |
|-------|---------|
| `modes` | List of valid mode names. First is the default. Arbitrary count/names. |
| `categories[]` | Ordered. Each has `id`, `label`, `metrics[]`. |
| `metric.id` | Stable key (payload + trigger text). |
| `metric.label` | Human display name. |
| `metric.unit` | Optional display unit (`"FPS"`, `"ms"`, `"%"`, `""`). |
| `metric.compute` | Registry key. Special key `constant` reads `params.value`. |
| `metric.params` | Optional dict passed to the computor. |
| `metric.direction` | `min` (pass if value ≥ threshold), `max` (≤), `eq` (==). |
| `metric.thresholds` | Map of mode-name → threshold value. Keys should cover `modes`. |
| `metric.hard` | Optional. Breach past this value → category **FAIL**. Absent → breach is only **WARN**. |
| `metric.trigger` | Action-trigger prefix emitted on breach. |

Config is loaded once and cached at module level (`_load_config()`), keyed by
resolved path. Default path: `dagster/benchmark_config.json` next to the module.

### 2. Registry

```python
_METRICS: dict[str, Callable] = {}

def metric(name):
    def deco(fn):
        _METRICS[name] = fn
        return fn
    return deco
```

Computor signature: `fn(runs, ctx, results, params) -> float | None`

- `runs` — `list[RunEntry]`.
- `ctx` — shared state computed once per evaluation:
  `total_runs, n_pass, n_fail, duration_hours, live_devices,
  live_device_serials, live_chipsets, run_devices, run_chipsets, by_stem`.
- `results` — `dict[metric_id, value]` computed so far this evaluation, in config
  order. Lets a metric read an earlier one (e.g. `delta_ram_emu` reads `r_leak`).
- `params` — the metric's config `params` dict (may be empty).

**A computor returns `None` when its required inputs are absent** (no runs, no
`fps_avg` samples, no probe field). No fabricated fallback values.

`constant` is a built-in computor: `return params["value"]`. Used only for genuine
fixed targets, never to fake a measurement.

Computors ported from current code (real data sources): `avg_fps`,
`combo_drop_fps`, `r_leak`, `a_fail_pct`, `r_crash_pct`, `r_softlock_pct`,
`delta_ram_emu` (reads `r_leak` from `results`), `e_scaling` (reads
`ctx.live_devices`), `unique_devices`, `unique_chipsets`.

Metrics that had **no real source** in the current code (`t_match_ms`,
`r_cv_error_pct`, `t_input_latency_ms`, `c_critical_pct`) are mapped in the
default config to computors that read a probe field which is currently absent, so
they return `None` → **N/A**. (When a probe later supplies these, the computor
returns the real value with no config change.)

### 3. Engine — `evaluate_game_benchmarks(runs, mode=None, config=None)`

Signature stays backward-compatible; adds optional `config` (dict or path).

1. `config = _resolve_config(config)` (default file if `None`).
2. `mode = mode or config["modes"][0]`. Validate `mode in config["modes"]`;
   unknown mode → raise `ValueError`.
3. Build `ctx` once (same live-device discovery + counts as today).
4. For each category, for each metric in order:
   - `value = _METRICS[m["compute"]](runs, ctx, results, m.get("params", {}))`
   - `results[m["id"]] = value`
   - Determine threshold: `m["thresholds"].get(mode)`.
   - Judge:
     - `value is None` → `passed = None`, `status = "N/A"`.
     - else compare by `direction` → `passed: bool`.
     - `hard` breach (value worse than `hard` in the `direction` sense) →
       metric contributes `FAIL` to category; plain threshold breach → `WARN`.
   - On breach (`passed is False`), append trigger string:
     `f"{m['trigger']}: {prefix}{m['label']} = {value}{unit} ({op} {threshold} limit)"`
     where `op` ∈ `{≥, ≤, =}` from `direction`, `prefix = "[<MODE>] "` when
     `mode != config["modes"][0]`.
5. Category status = worst of its non-N/A metrics (`FAIL` > `WARN` > `PASS`);
   all metrics N/A → category `"N/A"`.

### 4. Output payload

```json
{
  "mode": "normal",
  "live_devices": [ /* unchanged shape */ ],
  "categories": {
    "game_performance": {
      "label": "Game Performance",
      "status": "PASS",
      "metrics": [
        {
          "id": "avg_fps",
          "label": "Avg FPS",
          "value": 58.5,
          "unit": "FPS",
          "threshold": 50.0,
          "direction": "min",
          "passed": true
        },
        {
          "id": "t_match_ms",
          "label": "Image Match Time",
          "value": null,
          "unit": "ms",
          "threshold": 200.0,
          "direction": "max",
          "passed": null
        }
      ]
    }
  },
  "action_triggers": [ "OPTIMIZE_GRAPHICS: Avg FPS = 45.0 FPS (≥ 50.0 limit)" ]
}
```

- Top-level keys (`mode`, `live_devices`, `categories`, `action_triggers`)
  unchanged → `report_server.py` needs no edit.
- `categories` is now keyed by config `id`, each carrying `label`, `status`, and a
  generic ordered `metrics[]`. **No flat `avg_fps`-style aliases** (they would
  reintroduce fabricated defaults and defeat generic rendering).

### 5. Dashboard — `static/index.html`

Remove the four hardcoded metric cards and hardcoded display thresholds. Replace
with a generic loop over `gameBenchmarks.categories` and each category's
`metrics[]`:

```html
<template x-for="(cat, cid) in gameBenchmarks?.categories" :key="cid">
  <div class="bench-card glass-panel" :class="cat.status.toLowerCase()">
    <h3 x-text="cat.label"></h3>
    <span class="status-pill" :class="cat.status.toLowerCase()" x-text="cat.status"></span>
    <template x-for="m in cat.metrics" :key="m.id">
      <div class="bench-metric-row">
        <span x-text="m.label"></span>
        <strong x-text="m.value === null ? 'N/A' : m.value + (m.unit ? ' ' + m.unit : '')"></strong>
        <span x-text="m.passed === null ? '—' : (m.passed ? 'PASS' : 'BREACH')"
              :style="`color: ${m.passed===null ? 'var(--muted)' : m.passed ? 'var(--pass)' : 'var(--warn)'}`"></span>
        <small x-show="m.threshold !== null"
               x-text="`${m.direction==='min'?'≥':m.direction==='max'?'≤':'='} ${m.threshold} ${m.unit||''}`"></small>
      </div>
    </template>
  </div>
</template>
```

- Optional progress bar per metric: width = `Math.min(100, value/threshold*100)`,
  hidden when `value === null`. Pass/breach color from `m.passed`.
- Action-triggers banner (`x-for="tr in gameBenchmarks?.action_triggers"`) already
  generic — unchanged.
- Adding/removing a metric in config → a row appears/vanishes with no HTML change.

### 6. CLI — `benchmark.py::main` / `print_benchmark_table`

- Add `--config <path>` (default: shipped `benchmark_config.json`).
- Add `--mode <name>` (default: first config mode).
- `print_benchmark_table` iterates `categories`/`metrics` generically; prints
  `N/A` for `value is None`; prints threshold + direction. The per-stem runtime
  table (`compute_benchmarks`) is unchanged.

## Error handling

- Config file missing / invalid JSON → raise with the resolved path in the message.
- `compute` key not in registry → raise `KeyError` naming the metric id and key.
- `mode` not in `config["modes"]` → `ValueError` listing valid modes.
- Metric `thresholds` missing the active mode → treat threshold as `None`
  (metric still computes and displays a value, but `passed = None`, no trigger).
- Computor exception on one metric must not abort the whole evaluation — catch,
  set that metric to N/A, and continue. (Live-device discovery already wrapped in
  try/except today; keep that.)

## Testing — `tests/test_benchmarks.py` (rewrite)

Existing tests assert removed hardcoded keys; rewrite to the new structure. Keep
`PerformanceProbe` and `DeviceManager` tests as-is.

1. **Default-config pass:** real-data runs → known category `PASS`, no triggers.
2. **N/A behavior:** a metric whose inputs are absent → `passed is None`,
   `value is None`, excluded from rollup (category not dragged to FAIL by it), no
   trigger emitted for it.
3. **Breach + trigger:** low-FPS runs → `passed is False`, category `WARN`/`FAIL`
   per `hard`, matching trigger string present.
4. **Mode switch:** value passing `normal` threshold but failing a stricter mode's
   threshold → status differs by mode; non-default mode prefixes trigger with
   `[<MODE>]`.
5. **Arbitrary config:** inline config with a custom category + custom mode name +
   a `constant` metric → engine evaluates it correctly (proves data-driven count).
6. **Registry-missing / bad mode:** unknown `compute` key raises; unknown mode
   raises `ValueError`.

## Files touched

| File | Change |
|------|--------|
| `dagster/benchmark_config.json` | **new** — default 12-metric / 4-category config |
| `dagster/benchmark.py` | refactor `evaluate_game_benchmarks` → config-driven engine + registry; port 12 computors; add `--config`/`--mode`; generic table print |
| `static/index.html` | replace 4 hardcoded cards → generic category/metric loop |
| `dagster/tests/test_benchmarks.py` | rewrite benchmark tests to new structure |
| `dagster/report_server.py` | none (payload top-level shape preserved) |

## Migration safety

Default config = today's 12 metrics / 4 categories / same thresholds / same
`normal`+`aggressive` modes. Behavior is identical on ship, with one deliberate
correction: the four previously-faked metrics (`t_match_ms`, `r_cv_error_pct`,
`t_input_latency_ms`, `c_critical_pct`) now display **N/A** until a probe supplies
real data, instead of showing fabricated constants.
