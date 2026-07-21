"""Performance probing utility for sampling FPS, RAM usage, and engine metrics."""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class PerformanceProbe:
    """Samples game performance metrics (FPS, RAM, load time) during test runs."""

    def __init__(self, serial: str | None = None, package_name: str | None = None, interval: float = 2.0):
        import os
        self.serial = serial
        self.package_name = package_name or os.environ.get("GAME_PACKAGE", "com.woodpuzzle.pin3d")
        self.interval = interval

        self.fps_samples: list[float] = []
        self.ram_mb_samples: list[float] = []
        self.scene_loads: list[float] = []
        self.asset_errors: int = 0
        self.chipset: str = "unknown"
        self.net_profile: str = "unknown"

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self):
        """Start background performance sampling thread."""
        self._running = True
        if self.serial:
            try:
                adb_path = "adb"
                from dagster.device.device_manager import device_manager
                adb_path = device_manager.adb_path
                subprocess.run([adb_path, "-s", self.serial, "root"], capture_output=True, text=True, timeout=1.5)
            except Exception:
                pass
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self, out_dir: Path | None = None) -> dict:
        """Stop sampling, summarize metrics, and write perf_metrics.json if out_dir given."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        with self._lock:
            fps_avg = round(sum(self.fps_samples) / len(self.fps_samples), 1) if self.fps_samples else None
            fps_min = round(min(self.fps_samples), 1) if self.fps_samples else None
            ram_mb_peak = round(max(self.ram_mb_samples), 1) if self.ram_mb_samples else None
            ram_mb_delta = (
                round(max(self.ram_mb_samples) - min(self.ram_mb_samples), 1)
                if len(self.ram_mb_samples) >= 2
                else 0.0
            )
            scene_load_sec = round(sum(self.scene_loads) / len(self.scene_loads), 2) if self.scene_loads else None

            metrics = {
                "fps_avg": fps_avg,
                "fps_min": fps_min,
                "ram_mb_peak": ram_mb_peak,
                "ram_mb_delta": ram_mb_delta,
                "scene_load_sec": scene_load_sec,
                "asset_errors": self.asset_errors,
                "chipset": self.chipset,
                "net_profile": self.net_profile,
                "samples_count": len(self.fps_samples),
            }

        if out_dir:
            out_path = Path(out_dir) / "perf_metrics.json"
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(metrics, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to write perf_metrics.json: {e}")

        return metrics

    def record_scene_load(self, duration_sec: float):
        """Record a scene/level loading duration in seconds."""
        with self._lock:
            self.scene_loads.append(duration_sec)

    def record_asset_error(self):
        """Increment asset loading failure count."""
        with self._lock:
            self.asset_errors += 1

    def _sample_loop(self):
        while self._running:
            self._sample_once()
            time.sleep(self.interval)

    def _sample_once(self):
        if not self.serial or not self.package_name:
            return

        adb_path = "adb"
        try:
            from dagster.device.device_manager import device_manager
            adb_path = device_manager.adb_path
        except Exception:
            pass

        cmd_fps = [adb_path, "-s", self.serial, "shell", "dumpsys", "gfxinfo", self.package_name]
        cmd_mem = [adb_path, "-s", self.serial, "shell", "dumpsys", "meminfo", self.package_name]

        try:
            # Sample RAM usage
            res_mem = subprocess.run(cmd_mem, capture_output=True, text=True, timeout=2.0)
            if res_mem.returncode == 0:
                for line in res_mem.stdout.splitlines():
                    if "TOTAL" in line or "TOTAL PSS:" in line:
                        parts = line.split()
                        for p in parts:
                            if p.isdigit():
                                ram_kb = float(p)
                                with self._lock:
                                    self.ram_mb_samples.append(ram_kb / 1024.0)
                                break
                        break

            # Sample FPS estimate from gfxinfo frame stats
            res_fps = subprocess.run(cmd_fps, capture_output=True, text=True, timeout=2.0)
            if res_fps.returncode == 0 and "Profile data in ms" in res_fps.stdout:
                # Count total frames in standard 16.6ms budget
                lines = res_fps.stdout.splitlines()
                frame_times = []
                for line in lines:
                    parts = line.strip().split("\t")
                    if len(parts) >= 3:
                        try:
                            t = sum(float(x) for x in parts[:3])
                            if t > 0:
                                frame_times.append(t)
                        except ValueError:
                            pass
                if frame_times:
                    avg_frame_ms = sum(frame_times) / len(frame_times)
                    est_fps = min(60.0, 1000.0 / avg_frame_ms) if avg_frame_ms > 0 else 60.0
                    with self._lock:
                        self.fps_samples.append(est_fps)
        except Exception:
            pass
