"""Data layer for the global test report."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
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
            mtime = log_path.stat().st_mtime
            airtest_log = child / "airtest.log"
            if airtest_log.exists():
                mtime = max(mtime, airtest_log.stat().st_mtime)
            duration = max(0.0, mtime - when.timestamp())
        except OSError:
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
            )
        )
    entries.sort(key=lambda x: x.when, reverse=True)
    return entries


def compute_metrics(runs: list[RunEntry]) -> dict:
    """Compute aggregate metrics: totals, trend, and flaky tests."""
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
        
    # If there's only 1 point, add a dummy previous day so the line chart can draw a line
    if len(trend) == 1:
        from datetime import datetime, timedelta
        dt = datetime.strptime(trend[0]["date"], "%Y-%m-%d")
        prev_dt = dt - timedelta(days=1)
        trend.insert(0, {
            "date": prev_dt.strftime("%Y-%m-%d"),
            "total": 0,
            "pass_rate": trend[0]["pass_rate"]
        })
        
    # Flaky: tests flipping status across most recent 10 runs
    by_stem = {}
    for r in runs:
        # ignore unknown and skip for flaky detection
        if r.status in ("PASS", "FAIL"):
            by_stem.setdefault(r.stem, []).append(r)
            
    flaky_count = 0
    for stem, stem_runs in by_stem.items():
        stem_runs.sort(key=lambda x: x.when, reverse=True)
        recent_10 = stem_runs[:10]
        has_pass = any(r.status == "PASS" for r in recent_10)
        has_fail = any(r.status == "FAIL" for r in recent_10)
        if has_pass and has_fail:
            flaky_count += 1
            
    return {
        "total": total,
        "pass": n_pass,
        "fail": n_fail,
        "skip": n_skip,
        "unknown": n_unknown,
        "pass_rate": pass_rate,
        "trend": trend,
        "flaky": flaky_count,
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

