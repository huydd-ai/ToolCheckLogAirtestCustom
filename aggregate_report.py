"""Aggregate per-run report folders into a single global report.html."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
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


def group_by_date(entries: list[RunEntry]) -> list[tuple[str, list[RunEntry]]]:
    """Group entries by ISO date string (YYYY-MM-DD).

    Outer list ordered by date DESC. Inner lists ordered by datetime DESC.
    """
    by_date: dict[str, list[RunEntry]] = {}
    for e in entries:
        key = e.when.strftime("%Y-%m-%d")
        by_date.setdefault(key, []).append(e)
    for rows in by_date.values():
        rows.sort(key=lambda r: r.when, reverse=True)
    return sorted(by_date.items(), key=lambda kv: kv[0], reverse=True)


_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #222; }
h1 { margin: 0 0 16px; font-size: 22px; }
.empty { color: #888; font-style: italic; }
details { margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; }
details > summary { cursor: pointer; font-weight: 600; }
ul { list-style: none; padding: 0; margin: 8px 0 0; }
li { padding: 4px 0; display: flex; align-items: center; gap: 8px; }
.badge { display: inline-block; min-width: 48px; text-align: center; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; color: #fff; }
.badge.pass { background: #2e7d32; }
.badge.fail { background: #c62828; }
.badge.skip { background: #757575; }
.badge.unknown { background: #b58900; }
a { color: #1565c0; text-decoration: none; }
a:hover { text-decoration: underline; }
""".strip()


def _count_statuses(rows: list[RunEntry]) -> str:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    parts = []
    for s in ("PASS", "FAIL", "SKIP", "UNKNOWN"):
        if counts.get(s):
            parts.append(f"{counts[s]} {s}")
    return ", ".join(parts)


def render_html(groups: list[tuple[str, list[RunEntry]]]) -> str:
    today_str = date.today().strftime("%Y-%m-%d")
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>Dagster Test Reports</title>",
        f"<style>{_CSS}</style>",
        "</head><body>",
        "<h1>Dagster Test Reports</h1>",
    ]
    if not groups:
        parts.append('<p class="empty">No test runs found.</p>')
    for date_str, rows in groups:
        open_attr = " open" if date_str == today_str else ""
        summary = f"{escape(date_str)} — {escape(_count_statuses(rows))}"
        parts.append(f"<details{open_attr}><summary>{summary}</summary><ul>")
        for r in rows:
            status_cls = r.status.lower() if r.status in {"PASS", "FAIL", "SKIP"} else "unknown"
            href = escape(r.report_href, quote=True)
            stem = escape(r.stem)
            parts.append(
                f'<li><span class="badge {status_cls}">{escape(r.status)}</span>'
                f'<a href="{href}">{stem}</a></li>'
            )
        parts.append("</ul></details>")
    parts.append("</body></html>")
    return "\n".join(parts)
