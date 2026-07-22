"""Data layer for the global test report."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_FOLDER_RE = re.compile(r"^(.+)_(\d{8})_(\d{6})$")
_STATUS_RE = re.compile(r"^#\s*Status:\s*(PASS|FAIL|SKIP)\b", re.MULTILINE)
_DEVICE_RE = re.compile(r"^DEVICE=(.+)$", re.MULTILINE)
_AIR_PATH_RE = re.compile(r"^AIR_PATH=(.+)$", re.MULTILINE)
_FAIL_MSG_RE = re.compile(r",\s*FAIL,\s*(.+)$", re.MULTILINE)


def parse_run_folder_name(name: str) -> tuple[str, datetime] | None:
    m = _FOLDER_RE.match(name)
    if not m:
        return None
    stem, date_str, time_str = m.group(1), m.group(2), m.group(3)
    try:
        dt = datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if stem.startswith("_"):
        return None
    return stem, dt


@dataclass(frozen=True)
class RunEntry:
    stem: str
    when: datetime
    status: str
    folder: str
    report_href: str
    device: str = "unknown"
    suite: str = "unknown"
    duration: float | None = None
    error_summary: str | None = None
    fps_avg: float | None = None
    fps_min: float | None = None
    ram_mb_peak: float | None = None
    ram_mb_delta: float | None = None
    scene_load_sec: float | None = None
    asset_errors: int = 0
    chipset: str = "unknown"
    net_profile: str = "unknown"

    def to_dict(self):
        d = dict(self.__dict__)
        d['when'] = self.when.isoformat()
        return d


def extract_error_from_airtest_log(log_path: Path) -> str | None:
    """Read tail of airtest.log to find the last traceback line."""
    try:
        with log_path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk_size = min(size, 8192)
            f.seek(size - chunk_size, 0)
            tail = f.read().decode("utf-8", errors="replace")
            
        lines = tail.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith("DEBUG") and not line.startswith("INFO"):
                # Simple heuristic for traceback end or generic error line
                if "Error" in line or "Exception" in line or "Traceback" in line:
                    return line
        # Fallback to last non-empty line
        for line in reversed(lines):
            line = line.strip()
            if line:
                return line
    except OSError:
        pass
    return None


def scan_runs(report_root: Path) -> list[RunEntry]:
    if not report_root.exists():
        return []
    entries: list[RunEntry] = []
    for child in report_root.iterdir():
        if not child.is_dir():
            continue
        parsed = parse_run_folder_name(child.name)
        if parsed is None:
            continue
        log_path = child / "log.txt"
        if not log_path.exists():
            continue
            
        stem, when = parsed
        
        # Single head read
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                head = f.read(2048)  # Read a bit more to catch the error line if short
                if "# Status:" not in head:
                    f.seek(0)
                    head = f.read() # read full if status missing in head
        except OSError:
            continue
            
        # Parse fields
        status_match = _STATUS_RE.search(head)
        status = status_match.group(1) if status_match else "UNKNOWN"
        
        device_match = _DEVICE_RE.search(head)
        device = device_match.group(1).strip() if device_match else "unknown"
        
        suite_match = _AIR_PATH_RE.search(head)
        suite = Path(suite_match.group(1).strip()).parent.name if suite_match else "unknown"
        
        # Parse error summary
        error_summary = None
        if status == "FAIL":
            fail_match = _FAIL_MSG_RE.search(head)
            if fail_match:
                error_summary = fail_match.group(1).strip()
            else:
                airtest_log = child / "airtest.log"
                if airtest_log.exists():
                    error_summary = extract_error_from_airtest_log(airtest_log)
                    
        # Parse duration
        duration = None
        try:
            # Extract step timestamps (13-digit ms epoch) from log.txt
            ts_matches = [float(m.group(1)) / 1000.0 for m in re.finditer(r"(\d{13})\.jpg", head)]
            if len(ts_matches) >= 2:
                duration = max(0.0, max(ts_matches) - min(ts_matches))
            else:
                # Fallback to log file modification time vs folder creation time
                log_mtime = log_path.stat().st_mtime
                folder_ctime = child.stat().st_ctime
                duration = max(0.0, log_mtime - folder_ctime)
        except OSError:
            pass

        # Parse optional performance & infrastructure metrics
        fps_avg = None
        fps_min = None
        ram_mb_peak = None
        ram_mb_delta = None
        scene_load_sec = None
        asset_errors = 0
        chipset = "unknown"
        net_profile = "unknown"

        perf_json = child / "perf_metrics.json"
        if perf_json.exists():
            try:
                import json
                with perf_json.open("r", encoding="utf-8") as pf:
                    pdata = json.load(pf)
                    fps_avg = pdata.get("fps_avg")
                    fps_min = pdata.get("fps_min")
                    ram_mb_peak = pdata.get("ram_mb_peak")
                    ram_mb_delta = pdata.get("ram_mb_delta")
                    scene_load_sec = pdata.get("scene_load_sec")
                    asset_errors = pdata.get("asset_errors", 0)
                    chipset = pdata.get("chipset", "unknown")
                    net_profile = pdata.get("net_profile", "unknown")
            except Exception:
                pass

        entries.append(
            RunEntry(
                stem=stem,
                when=when,
                status=status,
                folder=child.name,
                report_href=f"{child.name}/report.html",
                device=device,
                suite=suite,
                duration=duration,
                error_summary=error_summary,
                fps_avg=fps_avg,
                fps_min=fps_min,
                ram_mb_peak=ram_mb_peak,
                ram_mb_delta=ram_mb_delta,
                scene_load_sec=scene_load_sec,
                asset_errors=asset_errors,
                chipset=chipset,
                net_profile=net_profile,
            )
        )
    entries.sort(key=lambda x: x.when, reverse=True)
    return entries


def compute_metrics(runs: list[RunEntry]) -> dict:
    """Compute aggregate metrics: totals, trend, flaky tests, and benchmark indicators."""
    total = len(runs)
    n_pass = sum(1 for r in runs if r.status == "PASS")
    n_fail = sum(1 for r in runs if r.status == "FAIL")
    n_skip = sum(1 for r in runs if r.status == "SKIP")
    n_unknown = sum(1 for r in runs if r.status == "UNKNOWN")
    
    pass_rate = round((n_pass / total) * 100) if total > 0 else 0
    
    # Trend: pass_rate by date
    by_date = {}
    for r in runs:
        d_str = r.when.strftime("%Y-%m-%d")
        if d_str not in by_date:
            by_date[d_str] = {"total": 0, "pass": 0}
        by_date[d_str]["total"] += 1
        if r.status == "PASS":
            by_date[d_str]["pass"] += 1
            
    trend = []
    for d_str in sorted(by_date.keys()):
        d_tot = by_date[d_str]["total"]
        d_pass = by_date[d_str]["pass"]
        d_rate = round((d_pass / d_tot) * 100) if d_tot > 0 else 0
        trend.append({"date": d_str, "total": d_tot, "pass_rate": d_rate})

    # Flaky: tests flipping status across most recent 10 runs
    by_stem = {}
    for r in runs:
        # ignore unknown and skip for flaky detection
        if r.status in ("PASS", "FAIL"):
            by_stem.setdefault(r.stem, []).append(r)
            
    flaky_stems = []
    for stem, stem_runs in by_stem.items():
        stem_runs.sort(key=lambda x: x.when, reverse=True)
        recent_10 = stem_runs[:10]
        has_pass = any(r.status == "PASS" for r in recent_10)
        has_fail = any(r.status == "FAIL" for r in recent_10)
        if has_pass and has_fail:
            flaky_stems.append(stem)

    flaky_count = len(flaky_stems)
    total_stems = len(by_stem)
    flaky_ratio = round((flaky_count / total_stems) * 100, 1) if total_stems > 0 else 0.0

    # Aggregate performance metrics across runs
    fps_vals = [r.fps_avg for r in runs if r.fps_avg is not None]
    avg_fps = round(sum(fps_vals) / len(fps_vals), 1) if fps_vals else None

    unique_devices = len({r.device for r in runs if r.device != "unknown"})
    unique_chipsets = len({r.chipset for r in runs if r.chipset != "unknown"})

    return {
        "total": total,
        "pass": n_pass,
        "fail": n_fail,
        "skip": n_skip,
        "unknown": n_unknown,
        "pass_rate": pass_rate,
        "trend": trend,
        "flaky": flaky_count,
        "flaky_ratio": flaky_ratio,
        "flaky_stems": flaky_stems,
        "avg_fps": avg_fps,
        "unique_devices": unique_devices,
        "unique_chipsets": unique_chipsets,
    }


def scan_catalog(test_root: Path) -> dict[str, list[str]]:
    """Map suite folder -> sorted .air stems under test_root/<suite>/."""
    if not test_root.exists():
        return {}
    catalog: dict[str, list[str]] = {}
    for air in test_root.glob("*/*.air"):
        catalog.setdefault(air.parent.name, []).append(air.stem)
    for stems in catalog.values():
        stems.sort()
    return dict(sorted(catalog.items()))

