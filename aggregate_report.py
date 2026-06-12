"""Aggregate per-run report folders into a single global report.html."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_FOLDER_RE = re.compile(r"^(.+)_(\d{8})_(\d{6})$")
_STATUS_RE = re.compile(r"^#\s*Status:\s*(PASS|FAIL|SKIP)\b", re.MULTILINE)


def parse_run_folder_name(name: str) -> tuple[str, datetime] | None:
    """Parse a run folder name `<stem>_YYYYMMDD_HHMMSS` -> (stem, datetime).

    Returns None when the name does not match the expected pattern (e.g. the
    `_parallel_<ts>` summary dir or unrelated folders).
    """
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


def extract_status(log_path: Path) -> str:
    """Return PASS/FAIL/SKIP from a run's `log.txt`, or UNKNOWN if missing.

    Reads only the first ~1 KiB - the header lives on line 3.
    """
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            head = f.read(1024)
    except OSError:
        return "UNKNOWN"
    m = _STATUS_RE.search(head)
    return m.group(1) if m else "UNKNOWN"


@dataclass(frozen=True)
class RunEntry:
    stem: str
    when: datetime
    status: str
    folder: str
    report_href: str


def scan_runs(report_root: Path) -> list[RunEntry]:
    """Find run folders under `report_root` that have a finished `log.txt`.

    In-progress runs (no log.txt yet) and unrelated folders (`_parallel_*`,
    arbitrary dirs) are skipped silently.
    """
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
        status = extract_status(log_path)
        entries.append(
            RunEntry(
                stem=stem,
                when=when,
                status=status,
                folder=child.name,
                report_href=f"{child.name}/report.html",
            )
        )
    return entries
