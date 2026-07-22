"""Unit tests for dagster game testing benchmark rule engine, probe, and metrics."""

import json
from datetime import datetime
from pathlib import Path

from dagster.reports.report_data import RunEntry, compute_metrics
from dagster.benchmark import compute_benchmarks, evaluate_game_benchmarks, metric, _METRICS, _resolve_config
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


def test_evaluate_game_benchmarks_pass():
    now = datetime.now()
    runs = [
        RunEntry(
            stem="tc01_login",
            when=now,
            status="PASS",
            folder="tc01_login_20260721_120000",
            report_href="href1",
            device="dev1",
            suite="Auth",
            duration=10.0,
            fps_avg=59.5,
            fps_min=57.0,
            ram_mb_peak=450.0,
            ram_mb_delta=2.0,
            asset_errors=0,
            chipset="Snapdragon8Gen2",
            net_profile="WiFi",
        ),
        RunEntry(
            stem="tc02_gameplay",
            when=now,
            status="PASS",
            folder="tc02_gameplay_20260721_120000",
            report_href="href2",
            device="dev1",
            suite="Core",
            duration=15.0,
            fps_avg=58.0,
            fps_min=55.0,
            ram_mb_peak=600.0,
            ram_mb_delta=5.0,
            asset_errors=0,
            chipset="Snapdragon8Gen2",
            net_profile="WiFi",
        ),
    ]

    bench_metrics = evaluate_game_benchmarks(runs)
    cats = bench_metrics["categories"]

    assert cats["performance"]["status"] == "PASS"
    assert cats["pipeline"]["status"] == "PASS"
    assert cats["suite_health"]["status"] == "PASS"
    assert cats["infrastructure"]["status"] == "PASS"
    assert len(bench_metrics["action_triggers"]) == 0


def test_all_12_puzzle_game_benchmark_formulas():
    now = datetime.now()
    runs = [
        RunEntry(
            stem="tc01_smoke",
            when=now,
            status="PASS",
            folder="tc01_smoke_20260721_120000",
            report_href="href1",
            device="dev1",
            suite="Smoke",
            duration=30.0,
            fps_avg=58.5,
            fps_min=56.0,
            ram_mb_peak=500.0,
            ram_mb_delta=0.0,
            asset_errors=0,
            chipset="Snapdragon",
        )
    ]
    res = evaluate_game_benchmarks(runs)
    gp = res["categories"]["game_performance"]
    es = res["categories"]["emulator_stability"]
    sq = res["categories"]["script_quality"]
    inf = res["categories"]["infrastructure"]

    # I. Game Performance
    assert "avg_fps" in gp and gp["avg_fps"] >= 55.0
    assert "combo_drop_fps" in gp and gp["combo_drop_fps"] <= 5.0
    assert "r_leak_mb_hr" in gp and gp["r_leak_mb_hr"] < 15.0
    assert "a_fail_pct" in gp and gp["a_fail_pct"] == 0.0

    # II. Emulator Stability
    assert "r_crash_pct" in es and es["r_crash_pct"] < 0.5
    assert "r_softlock_pct" in es and es["r_softlock_pct"] < 1.0
    assert "delta_ram_emu_mb_hr" in es and es["delta_ram_emu_mb_hr"] < 50.0
    assert "e_scaling_pct" in es and es["e_scaling_pct"] >= 85.0

    # III. Airtest Script Quality
    assert "t_match_ms" in sq and sq["t_match_ms"] < 200.0
    assert "r_cv_error_pct" in sq and sq["r_cv_error_pct"] == 0.0
    assert "t_input_latency_ms" in sq and sq["t_input_latency_ms"] < 120.0
    assert "c_critical_pct" in sq and sq["c_critical_pct"] == 100.0

    # IV. Active Test Farm Hardware
    assert "unique_devices" in inf


def test_evaluate_game_benchmarks_action_triggers():
    now = datetime.now()
    runs = [
        RunEntry(
            stem="tc01_laggy",
            when=now,
            status="FAIL",
            folder="tc01_laggy_20260721_120000",
            report_href="href1",
            device="dev1",
            suite="Core",
            duration=100.0,
            fps_avg=45.0,  # Avg FPS < 50 FPS benchmark limit
            fps_min=45.0,
            ram_mb_peak=900.0,
            ram_mb_delta=25.0,
            asset_errors=2,
            chipset="LowEndChip",
        ),
        RunEntry(
            stem="tc01_laggy",
            when=now,
            status="PASS",
            folder="tc01_laggy_20260721_110000",
            report_href="href2",
            device="dev1",
            suite="Core",
            duration=100.0,
            fps_avg=45.0,
            fps_min=45.0,
            ram_mb_peak=900.0,
            ram_mb_delta=25.0,
            asset_errors=1,
            chipset="LowEndChip",
        ),
    ]

    bench_metrics = evaluate_game_benchmarks(runs)
    triggers = bench_metrics["action_triggers"]

    assert any("OPTIMIZE_GRAPHICS" in t or "HALT_BUILD" in t for t in triggers)


def test_evaluate_game_benchmarks_aggressive_mode():
    now = datetime.now()
    runs = [
        RunEntry(
            stem="tc01_minor_drop",
            when=now,
            status="PASS",
            folder="tc01_minor_drop_20260721_120000",
            report_href="href1",
            device="dev1",
            suite="Core",
            duration=10.0,
            fps_avg=52.0,  # 52 FPS passes normal 50 FPS limit, fails aggressive 55 FPS limit
            fps_min=50.0,
            scene_load_sec=2.5,
            ram_mb_peak=400.0,
            ram_mb_delta=0.0,
            asset_errors=0,
            chipset="Snapdragon8Gen2",
        )
    ]

    normal_res = evaluate_game_benchmarks(runs, mode="normal")
    assert normal_res["categories"]["game_performance"]["status"] == "PASS"

    aggr_res = evaluate_game_benchmarks(runs, mode="aggressive")
    assert aggr_res["mode"] == "aggressive"
    assert len(aggr_res["action_triggers"]) > 0
    assert any("[AGGRESSIVE]" in t for t in aggr_res["action_triggers"])
    assert any("OPTIMIZE_GRAPHICS" in t for t in aggr_res["action_triggers"])


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
