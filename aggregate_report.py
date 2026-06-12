"""Aggregate per-run report folders into a single global report.html."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_FOLDER_RE = re.compile(r"^(.+)_(\d{8})_(\d{6})$")


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
