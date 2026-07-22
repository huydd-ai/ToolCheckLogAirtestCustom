"""Unit tests for dagster game testing benchmark rule engine, probe, and metrics."""

import json
from datetime import datetime as _dt
from pathlib import Path

from dagster.reports.report_data import RunEntry, compute_metrics
from dagster.benchmark import compute_benchmarks, evaluate_game_benchmarks, metric, _METRICS, _resolve_config, _build_ctx
from dagster.capture.performance_probe import PerformanceProbe
from dagster.device.device_manager import DeviceManager, DeviceCaps


def test_metric_decorator_registers():
    @metric("unit_test_probe")
    def _probe(runs, ctx, results, params):
        return 1.0

    assert _METRICS["unit_test_probe"] is _probe
    assert _resolve_config(None)["modes"][0] == "normal"


def test_resolve_config_passthrough_dict():
    cfg = {"modes": ["x"], "categories": []}
    assert _resolve_config(cfg) is cfg


def _run(stem, status, fps_avg, fps_min, ram_delta, asset_errors=0, dur=10.0, chip="Snap"):
    return RunEntry(stem=stem, when=_dt.now(), status=status,
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
    # ram_delta kept tiny (not 1.0/2.0): with dur=10.0 the duration_hours denominator is
    # ~0.0056h, so r_leak = sum(delta)/hours blows up past the 15 MB/hr threshold at 1.0+2.0.
    # 0.01 each keeps r_leak comfortably under threshold so this stays an all-PASS fixture.
    runs = [_run("tc01", "PASS", 58.0, 55.0, 0.01), _run("tc02", "PASS", 59.0, 56.0, 0.01)]
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
    # fps_min=56 (not 50): combo_drop_fps = 60 - fps_min must stay <= 5.0 (normal threshold)
    # so game_performance is all-PASS under normal mode; only avg_fps=52 is meant to trip here
    # (passes normal(50), fails aggressive(55)).
    runs = [_run("tc01", "PASS", 52.0, 56.0, 0.0)]
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


def test_performance_probe_stop_writes_json(tmp_path: Path):
    probe = PerformanceProbe(interval=0.1)
    probe.fps_samples = [60.0, 58.0, 59.0]
    probe.ram_mb_samples = [400.0, 410.0, 420.0]
    probe.record_scene_load(3.5)
    probe.record_asset_error()

    metrics = probe.stop(out_dir=tmp_path)

    assert metrics["fps_avg"] == 59.0
    assert metrics["ram_mb_peak"] == 420.0
    assert metrics["asset_errors"] == 1
    assert (tmp_path / "perf_metrics.json").exists()

    with (tmp_path / "perf_metrics.json").open("r", encoding="utf-8") as f:
        loaded = json.load(f)
        assert loaded["fps_avg"] == 59.0
        assert loaded["asset_errors"] == 1


def test_device_manager_network_emulation():
    dm = DeviceManager()
    dm.devices["emulator-5554"] = DeviceCaps(
        serial="emulator-5554",
        is_rooted=True,
        android_version="11",
        resolution="1080x1920",
        chipset="x86_64",
        ram_gb=4.0,
        net_profile="WiFi",
    )

    success = dm.set_network_emulation_profile("emulator-5554", "3G")
    assert success is True
    assert dm.devices["emulator-5554"].net_profile == "3G"


def _ctx(runs):
    # minimal ctx builder mirroring engine (Task 3 builds the real one)
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


def test_print_table_generic_na(capsys):
    from dagster.benchmark import print_benchmark_table
    runs = [_run("tc01", "PASS", 58.0, 55.0, 1.0)]
    gb = evaluate_game_benchmarks(runs)
    print_benchmark_table({}, gb)
    out = capsys.readouterr().out
    assert "Game Performance" in out
    assert "Avg FPS" in out
    assert "N/A" in out   # script_quality metrics render N/A
