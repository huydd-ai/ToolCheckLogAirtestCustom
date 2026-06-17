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
    by_date: dict[str, list[RunEntry]] = {}
    for e in entries:
        key = e.when.strftime("%Y-%m-%d")
        by_date.setdefault(key, []).append(e)
    for rows in by_date.values():
        rows.sort(key=lambda r: r.when, reverse=True)
    return sorted(by_date.items(), key=lambda kv: kv[0], reverse=True)

_CSS = """
:root {
  --bg: #0f1115;
  --bg-card: #1a1d24;
  --bg-item: #252a33;
  --text-main: #e2e8f0;
  --text-dim: #94a3b8;
  --border: #334155;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --pass: #10b981;
  --fail: #ef4444;
  --skip: #64748b;
  --r: 8px;
}
body { 
  font-family: 'Inter', -apple-system, sans-serif; 
  background: var(--bg); 
  color: var(--text-main); 
  margin: 0; 
  padding: 40px 24px;
}
.container { 
  max-width: 900px; 
  margin: 0 auto; 
}
h1 { 
  font-size: 28px; 
  font-weight: 700; 
  margin-bottom: 24px; 
  display: flex;
  align-items: center;
  gap: 12px;
}
details { 
  background: var(--bg-card); 
  border: 1px solid var(--border); 
  border-radius: var(--r); 
  margin-bottom: 16px; 
  overflow: hidden;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
summary { 
  padding: 16px 20px; 
  font-weight: 600; 
  font-size: 16px; 
  cursor: pointer; 
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
  background: var(--bg-card);
  transition: background 0.2s;
}
summary:hover { background: var(--bg-item); }
.summary-left { display: flex; align-items: center; gap: 16px; }
.delete-all-btn {
  background: transparent;
  color: var(--fail);
  border: 1px solid var(--fail);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.delete-all-btn:hover {
  background: var(--fail);
  color: #fff;
}
.group-content { padding: 0 20px 20px; }
ul { list-style: none; padding: 0; margin: 0; }
li { 
  display: flex; 
  align-items: center; 
  justify-content: space-between;
  padding: 12px 16px; 
  background: var(--bg-item);
  border-radius: var(--r);
  margin-top: 8px;
  border: 1px solid transparent;
  transition: all 0.2s;
}
li:hover { border-color: var(--border); transform: translateX(4px); }
.run-main { display: flex; align-items: center; gap: 16px; }
.badge { 
  padding: 4px 12px; 
  border-radius: 20px; 
  font-size: 11px; 
  font-weight: 700; 
  text-transform: uppercase;
  min-width: 48px;
  text-align: center;
  letter-spacing: 0.5px;
}
.badge.pass { background: rgba(16, 185, 129, 0.15); color: var(--pass); border: 1px solid rgba(16,185,129,0.3); }
.badge.fail { background: rgba(239, 68, 68, 0.15); color: var(--fail); border: 1px solid rgba(239,68,68,0.3); }
.badge.skip { background: rgba(100, 116, 139, 0.15); color: var(--skip); border: 1px solid rgba(100,116,139,0.3); }
.run-name { color: var(--text-main); font-weight: 500; text-decoration: none; transition: color 0.2s; }
.run-name:hover { color: var(--accent); }
.run-meta { display: flex; align-items: center; gap: 16px; }
.run-time { color: var(--text-dim); font-size: 13px; font-variant-numeric: tabular-nums; }
.delete-btn {
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.delete-btn:hover { background: rgba(239,68,68,0.1); color: var(--fail); }
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-dim);
  background: var(--bg-card);
  border-radius: var(--r);
  border: 1px dashed var(--border);
  font-size: 15px;
}

/* Modal */
#modal {
  display: none; position: fixed; inset: 0; z-index: 100;
  align-items: center; justify-content: center;
  backdrop-filter: blur(4px);
}
#modal-bg { position: absolute; inset: 0; background: rgba(0,0,0,0.6); }
#modal-panel {
  position: relative; z-index: 101; width: 92%; height: calc(100vh - 64px);
  background: #fff; border: 1px solid var(--border); border-radius: var(--r);
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 24px 64px rgba(0,0,0,0.8);
}
#modal-bar {
  padding: 10px 16px; background: var(--bg); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px; flex-shrink: 0;
}
#modal-title {
  color: var(--text-main); font-family: monospace; font-size: 13px; flex: 1;
}
#modal-close {
  background: none; border: 1px solid var(--border); color: var(--text-dim);
  width: 28px; height: 28px; border-radius: 6px; cursor: pointer;
}
#modal-close:hover { background: var(--bg-item); color: #fff; }
#modal-frame { flex: 1; border: none; background: #fff; }
""".strip()

_JS = """
var _modal = document.getElementById('modal');
var _frame = document.getElementById('modal-frame');
var _title = document.getElementById('modal-title');

function openReport(e, href, stem) {
  e.preventDefault();
  _frame.src = href;
  _title.textContent = stem;
  _modal.style.display = 'flex';
}

function closeReport() {
  _modal.style.display = 'none';
  _frame.src = '';
}

document.getElementById('modal-bg').addEventListener('click', closeReport);
document.getElementById('modal-close').addEventListener('click', closeReport);
document.addEventListener('keydown', function(e) { if(e.key === 'Escape') closeReport(); });

function checkEmpty() {
  if (!document.querySelector('.group-content')) {
    var e = document.createElement('p');
    e.className = 'empty-state';
    e.textContent = 'No test runs found. Generate some reports to see them here!';
    document.querySelector('.container').appendChild(e);
  }
}

async function deleteRun(e, folder) {
  e.stopPropagation();
  if (!confirm('Delete: ' + folder + '?')) return;
  try {
    const r = await fetch('/delete/' + encodeURIComponent(folder), {method: 'POST'});
    if (r.ok) {
      window.location.href = window.location.pathname + '?t=' + new Date().getTime();
    } else {
      alert('Delete failed (' + r.status + '): ' + await r.text());
    }
  } catch (err) {
    alert('Server offline. Open via http://localhost:7070/report.html');
  }
}

async function deleteAllRuns(btn, dateStr) {
  if (!confirm('Delete all test runs on ' + dateStr + '?')) return;
  btn.disabled = true;
  try {
    const r = await fetch('/delete-date/' + encodeURIComponent(dateStr), {method: 'POST'});
    if (r.ok) {
      window.location.href = window.location.pathname + '?t=' + new Date().getTime();
    } else {
      alert('Delete failed (' + r.status + '): ' + await r.text());
    }
  } catch (err) {
    alert('Server offline. Open via http://localhost:7070/report.html');
  }
}

// Disable if file://
(function(){
  if(location.protocol === 'file:') {
    var b = document.getElementById('banner');
    if(b) {
      b.style.display = 'block';
      b.textContent = 'Delete buttons disabled (file:// protocol). Run: python report_server.py and open http://localhost:7070/report.html';
    }
    document.querySelectorAll('.delete-btn, .delete-all-btn').forEach(btn => btn.remove());
  }
})();
"""

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
    html = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>Dagster Test Reports</title>',
        f'<style>{_CSS}</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        '<h1>Dagster Test Reports</h1>',
        '<div id="banner" style="display:none; background:rgba(239,68,68,0.15); border:1px solid var(--fail); color:var(--fail); padding:12px; border-radius:8px; margin-bottom:16px; font-size:14px;"></div>'
    ]
    
    if not groups:
        html.append('<p class="empty-state">No test runs found. Generate some reports to see them here!</p>')
    else:
        for date_str, rows in groups:
            open_attr = " open" if date_str == today_str else ""
            summary = f"{escape(date_str)} &mdash; {escape(_count_statuses(rows))}"
            html.append(f'<details{open_attr}>')
            html.append('<summary>')
            html.append(f'<div class="summary-left"><span>{summary}</span></div>')
            html.append(f'<button class="delete-all-btn" onclick="deleteAllRuns(this, \'{escape(date_str)}\')">Delete All</button>')
            html.append('</summary>')
            html.append('<div class="group-content"><ul>')
            
            for r in rows:
                status_cls = r.status.lower() if r.status in {"PASS", "FAIL", "SKIP"} else "unknown"
                href = escape(r.report_href, quote=True)
                stem = escape(r.stem)
                folder = escape(r.folder)
                time_str = r.when.strftime("%H:%M:%S")
                
                html.append('<li class="run-item">')
                html.append('<div class="run-main">')
                html.append(f'<span class="badge {status_cls}">{escape(r.status)}</span>')
                html.append(f'<a class="run-name" href="{href}" onclick="openReport(event, \'{href}\', \'{stem}\')">{stem}</a>')
                html.append('</div>')
                html.append('<div class="run-meta">')
                html.append(f'<span class="run-time">{time_str}</span>')
                html.append(f'<button class="delete-btn" title="Delete Report" onclick="deleteRun(event, \'{folder}\')">')
                html.append('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>')
                html.append('</button>')
                html.append('</div>')
                html.append('</li>')
                
            html.append('</ul></div></details>')
            
    html.append('</div>') # end container
    
    # Modal HTML
    html.append('<div id="modal"><div id="modal-bg"></div><div id="modal-panel">')
    html.append('<div id="modal-bar"><div id="modal-title"></div><button id="modal-close">x</button></div>')
    html.append('<iframe id="modal-frame"></iframe></div></div>')
    
    html.append(f'<script>{_JS}</script>')
    html.append('</body></html>')
    return "\n".join(html)

def regenerate_global_report(report_root: Path) -> Path:
    report_root.mkdir(parents=True, exist_ok=True)
    entries = scan_runs(report_root)
    groups = group_by_date(entries)
    html = render_html(groups)
    out = report_root / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == '__main__':
    regenerate_global_report(Path(__file__).parent / 'report_run')
