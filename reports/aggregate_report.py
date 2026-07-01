"""Aggregate per-run report folders into a single global report.html."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path


def _js_arg(s: str) -> str:
    """Escape a value for use as a single-quoted JS string literal inside a
    double-quoted HTML attribute, e.g. onclick="fn('<here>')". JS-escape first
    (backslash, quote), then HTML-escape so the attribute can't be broken out of.
    Windows filenames can't contain " or \\, but ' is legal — this closes that gap."""
    s = s.replace("\\", "\\\\").replace("'", "\\'")
    return escape(s, quote=True)

try:
    from dagster.reports.report_theme import THEME_CSS
    from dagster.reports.report_data import RunEntry, scan_runs, scan_catalog, parse_run_folder_name
except ModuleNotFoundError:
    from report_theme import THEME_CSS
    from report_data import RunEntry, scan_runs, scan_catalog, parse_run_folder_name

def build_catalog(
    test_root: Path, entries: list[RunEntry]
) -> list[tuple[str, list[dict]]]:
    """Join scan_catalog() with run history on (suite, stem). Each test gets its
    newest run's status + report href (or None if never run)."""
    newest: dict[tuple[str, str], RunEntry] = {}
    for e in entries:
        key = (e.suite, e.stem)
        if key not in newest or e.when > newest[key].when:
            newest[key] = e
    out: list[tuple[str, list[dict]]] = []
    for suite, stems in scan_catalog(test_root).items():
        tests = []
        for stem in stems:
            run = newest.get((suite, stem))
            tests.append({
                "stem": stem,
                "air_path": f"{test_root.name}/{suite}/{stem}.air",
                "last_status": run.status if run else None,
                "last_href": run.report_href if run else None,
            })
        out.append((suite, tests))
    return out

def group_by_date(entries: list[RunEntry]) -> list[tuple[str, list[RunEntry]]]:
    by_date: dict[str, list[RunEntry]] = {}
    for e in entries:
        key = e.when.strftime("%Y-%m-%d")
        by_date.setdefault(key, []).append(e)
    for rows in by_date.values():
        rows.sort(key=lambda r: r.when, reverse=True)
    return sorted(by_date.items(), key=lambda kv: kv[0], reverse=True)

def group_by_suite_then_date(
    entries: list[RunEntry],
) -> list[tuple[str, list[tuple[str, list[RunEntry]]]]]:
    by_suite: dict[str, list[RunEntry]] = {}
    for e in entries:
        by_suite.setdefault(e.suite, []).append(e)
    # "unknown" sorts last, others alphabetical
    suite_keys = sorted(by_suite, key=lambda s: (s == "unknown", s))
    return [(s, group_by_date(by_suite[s])) for s in suite_keys]

_CSS = """
body { padding: 40px 24px; }
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
.run-main { display: flex; align-items: center; gap: 16px; flex: 1; min-width: 0; }
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
.run-name { color: var(--text-main); font-weight: 500; text-decoration: none; transition: color 0.2s; word-break: break-word; white-space: pre-wrap; display: block; }
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
.rerun-btn {
  background: none;
  border: 1px solid var(--accent);
  color: var(--accent);
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}
.rerun-btn:hover { background: rgba(59,130,246,0.15); }
.rerun-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.rerun-status {
  font-size: 11px;
  color: var(--text-dim);
  min-width: 64px;
}
.terminate-btn {
  background: none; border: 1px solid var(--fail); color: var(--fail);
  cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;
  transition: all 0.2s; display: none;
}
.terminate-btn:hover { background: rgba(239,68,68,0.15); }
.logs-btn {
  background: none; border: 1px solid var(--text-dim); color: var(--text-dim);
  cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;
  transition: all 0.2s; display: none;
}
.logs-btn:hover { background: rgba(148,163,184,0.15); color: #fff; }
.run-logs-container {
  display: none; flex-direction: column; background: #000; color: #0f0;
  font-family: monospace; padding: 10px; font-size: 12px; max-height: 300px;
  overflow-y: auto; border-radius: 4px; margin-top: 4px; margin-bottom: 8px;
}
.run-logs-container pre { margin: 0; white-space: pre-wrap; }
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
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--r);
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
#modal-frame { flex: 1; border: none; background: var(--bg); }

/* Summary bar */
.summary-bar {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
}
.metric {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r);
  padding: 14px 18px;
}
.metric .label { font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .05em; }
.metric .value { font-size: 26px; font-weight: 700; margin-top: 4px; }
.metric .value.pass { color: var(--pass); }
.metric .value.fail { color: var(--fail); }

/* Controls */
.controls { display: flex; gap: 10px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
#dash-search {
  flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid var(--border);
  border-radius: var(--r); background: var(--bg-card); color: var(--text-main); font-size: 14px; outline: none;
}
#dash-search:focus { border-color: var(--accent); }
.filter-pill {
  padding: 7px 14px; border: 1px solid var(--border); border-radius: var(--r);
  background: var(--bg-card); color: var(--text-dim); cursor: pointer; font-size: 13px; font-weight: 600;
}
.filter-pill:hover { background: var(--bg-item); }
.filter-pill.active { background: var(--accent); border-color: var(--accent); color: #fff; }

/* Device summary */
.device-bar { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }
.device-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r); padding: 14px 16px;
  cursor: pointer; transition: border-color 0.2s;
}
.device-card:hover { border-color: var(--accent); }
.device-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.device-card .dev-id { font-family: ui-monospace, Consolas, monospace; font-size: 13px; color: var(--text-main); font-weight: 600; word-break: break-all; }
.device-card .dev-counts { display: flex; gap: 12px; margin-top: 8px; font-size: 13px; font-weight: 700; }
.device-card .dev-counts .p { color: var(--pass); }
.device-card .dev-counts .f { color: var(--fail); }
.device-card .dev-counts .s { color: var(--skip); }
.device-card .dev-last { font-size: 11px; color: var(--text-dim); margin-top: 6px; }
.dev-tag {
  font-family: ui-monospace, Consolas, monospace; font-size: 11px; color: var(--text-dim);
  background: var(--bg); border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; white-space: nowrap;
}
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab-btn { background: var(--bg); border: 1px solid var(--border); color: var(--text-dim); padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.tab-btn.active { color: var(--text-main); border-color: var(--accent); }
.tab-pane { display: none; }
.tab-pane.active { display: block; }
.suite-summary { font-weight: 700; }
.suite-content { padding-left: 8px; }
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

var _runsEtag = '';
var _activeRuns = 0;
var _runOffsets = {};

function toggleLogs(folder) {
  var el = document.getElementById('logs-' + folder);
  el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'flex' : 'none';
}

async function terminateTest(btn, folder) {
  if (!confirm('Terminate running test?')) return;
  var jobId = btn.getAttribute('data-job-id');
  if (!jobId) return;
  btn.disabled = true;
  try {
    await fetch('/rerun-terminate/' + encodeURIComponent(jobId), {method: 'POST'});
  } catch (err) {}
}

async function rerunTest(btn, folder) {
  btn.disabled = true;
  btn.textContent = '…';
  var statusEl = document.querySelector('.rerun-status[data-folder="' + folder + '"]');
  var termBtn = document.querySelector('.terminate-btn[data-folder="' + folder + '"]');
  var logsBtn = document.querySelector('.logs-btn[data-folder="' + folder + '"]');
  var preEl = document.getElementById('pre-' + folder);
  var logsContainer = document.getElementById('logs-' + folder);

  if (statusEl) statusEl.textContent = 'Starting…';
  try {
    var r = await fetch('/rerun/' + encodeURIComponent(folder), {method: 'POST'});
    var data = await r.json();
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '↺ Rerun';
      if (statusEl) statusEl.textContent = data.error || 'Error';
      return;
    }
    if (statusEl) statusEl.textContent = 'Running…';
    
    if (termBtn) {
      termBtn.style.display = 'inline-block';
      termBtn.disabled = false;
      termBtn.setAttribute('data-job-id', data.job_id);
    }
    if (logsBtn) logsBtn.style.display = 'inline-block';
    if (preEl) preEl.textContent = 'Waiting for logs...\\n';
    if (logsContainer) logsContainer.style.display = 'flex';
    
    _runOffsets[data.job_id] = 0;
    _activeRuns++;
    pollRerunStatus(btn, folder, data.job_id, statusEl, termBtn, logsBtn, preEl, logsContainer);
  } catch (err) {
    btn.disabled = false;
    btn.textContent = '↺ Rerun';
    if (statusEl) statusEl.textContent = 'Server offline';
  }
}

function pollRerunStatus(btn, folder, jobId, statusEl, termBtn, logsBtn, preEl, logsContainer, onComplete) {
  var intervalId = setInterval(async function() {
    try {
      var off = _runOffsets[jobId] || 0;
      var lr = await fetch('/rerun-logs/' + encodeURIComponent(jobId) + '?offset=' + off);
      var ldata = await lr.json();
      if (ldata.text) {
        if (preEl.textContent === 'Waiting for logs...\\n') preEl.textContent = '';
        preEl.textContent += ldata.text;
        if (logsContainer) logsContainer.scrollTop = logsContainer.scrollHeight;
      }
      _runOffsets[jobId] = ldata.offset;
    } catch(e) {}

    try {
      var r = await fetch('/rerun-status/' + encodeURIComponent(jobId));
      var data = await r.json();
      if (data.status !== 'running') {
        clearInterval(intervalId);
        _activeRuns = Math.max(0, _activeRuns - 1);
        btn.disabled = false;
        btn.textContent = btn.hasAttribute('data-is-catalog') ? '▶ Run' : '↺ Rerun';
        if (termBtn) termBtn.style.display = 'none';
        if (statusEl) statusEl.textContent = data.status === 'done' ? '✓ Done' : '✗ Failed';
        if (typeof onComplete === 'function') onComplete(); else refreshRunList();
      }
    } catch (err) {
      clearInterval(intervalId);
      _activeRuns = Math.max(0, _activeRuns - 1);
      btn.disabled = false;
      btn.textContent = btn.hasAttribute('data-is-catalog') ? '▶ Run' : '↺ Rerun';
      if (termBtn) termBtn.style.display = 'none';
      if (statusEl) statusEl.textContent = 'Error';
      if (typeof onComplete === 'function') onComplete();
    }
  }, 2000);
}

async function refreshRunList() {
  if (_activeRuns > 0 || _isQueueRunning) return;  // don't reload mid-rerun — it'd kill the live log view
  try {
    var headers = _runsEtag ? {'If-None-Match': _runsEtag} : {};
    var r = await fetch('/api/runs', {headers: headers});
    if (r.status === 304) return;
    if (!r.ok) return;
    _runsEtag = r.headers.get('ETag') || '';
    window.location.href = window.location.pathname + '?t=' + new Date().getTime();
  } catch (err) {
    // server offline — skip refresh
  }
}

// Auto-refresh: seed the current ETag once (so we don't reload on the first poll),
// then poll /api/runs — a new/deleted report folder changes the ETag and triggers reload.
async function startAutoRefresh() {
  try {
    var r = await fetch('/api/runs');
    if (r.ok) _runsEtag = r.headers.get('ETag') || '';
  } catch (err) {}
  setInterval(refreshRunList, 5000);
}
startAutoRefresh();

var _deviceFilter = null;

function toggleDevice(card) {
  var dev = card.getAttribute('data-device');
  if (_deviceFilter === dev) {
    _deviceFilter = null;
    card.classList.remove('active');
  } else {
    _deviceFilter = dev;
    document.querySelectorAll('.device-card').forEach(function(c) { c.classList.remove('active'); });
    card.classList.add('active');
  }
  applyDashboardFilters();
}
var _runQueue = [];
var _isQueueRunning = false;

async function runAllTests(btn) {
  var details = btn.closest('details');
  var rerunBtns = details.querySelectorAll('.run-meta .rerun-btn:not(.run-all-btn)');
  if (rerunBtns.length === 0) return;
  
  btn.disabled = true;
  var origText = btn.textContent;
  btn.textContent = 'Running All…';
  
  for (var i = 0; i < rerunBtns.length; i++) {
    var b = rerunBtns[i];
    var match = b.getAttribute('onclick').match(/runCatalogTest\(this,\s*'([^']+)',\s*'([^']+)'\)/);
    if (match) {
      _runQueue.push({ btn: b, key: match[1], airPath: match[2] });
    }
  }
  
  if (!_isQueueRunning) {
    _isQueueRunning = true;
    await processRunQueue();
  }
  
  btn.textContent = origText;
  btn.disabled = false;
}

async function processRunQueue() {
  while (_runQueue.length > 0) {
    var task = _runQueue.shift();
    await new Promise(resolve => {
      runCatalogTest(task.btn, task.key, task.airPath, resolve);
    });
  }
  _isQueueRunning = false;
  refreshRunList();
}

function applyDashboardFilters() {
  var searchEl = document.getElementById('dash-search');
  var q = (searchEl ? searchEl.value : '').toLowerCase();
  var active = document.querySelector('.filter-pill.active');
  var sf = active ? active.getAttribute('data-status') : 'all';
  document.querySelectorAll('details').forEach(function(d) {
    var visible = 0;
    d.querySelectorAll('.run-item').forEach(function(li) {
      var name = li.getAttribute('data-name') || '';
      var st = li.getAttribute('data-status') || '';
      var dev = li.getAttribute('data-device') || '';
      var show = true;
      if (sf !== 'all' && st !== sf) show = false;
      if (_deviceFilter && dev !== _deviceFilter) show = false;
      if (q && name.indexOf(q) === -1) show = false;
      li.style.display = show ? '' : 'none';
      var logs = li.nextElementSibling;
      if (logs && logs.classList.contains('run-logs-container') && !show) logs.style.display = 'none';
      if (show) visible++;
    });
    d.style.display = visible ? '' : 'none';
  });
}

(function() {
  var searchEl = document.getElementById('dash-search');
  if (searchEl) searchEl.addEventListener('input', applyDashboardFilters);
  document.querySelectorAll('.filter-pill').forEach(function(p) {
    p.addEventListener('click', function() {
      document.querySelectorAll('.filter-pill').forEach(function(x) { x.classList.remove('active'); });
      this.classList.add('active');
      applyDashboardFilters();
    });
  });
})();

function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  var pane = document.getElementById('tab-' + name);
  if (pane) pane.classList.add('active');
  var btn = document.querySelector('.tab-btn[data-tab="' + name + '"]');
  if (btn) btn.classList.add('active');
}

async function runCatalogTest(btn, key, airPath, onComplete) {
  btn.disabled = true;
  btn.setAttribute('data-is-catalog', 'true');
  var orig = btn.textContent;
  btn.textContent = '…';
  var statusEl = document.getElementById('cat-status-' + key);
  var termBtn = document.getElementById('cat-term-' + key);
  var preEl = document.getElementById('pre-' + key);
  var logsContainer = document.getElementById('logs-' + key);
  if (statusEl) statusEl.textContent = 'Starting…';
  try {
    var r = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({air_path: airPath})
    });
    var data = await r.json();
    if (!r.ok) {
      btn.disabled = false; btn.textContent = orig;
      if (statusEl) statusEl.textContent = data.error || 'Error';
      return;
    }
    if (statusEl) statusEl.textContent = 'Running…';
    if (termBtn) { termBtn.style.display = 'inline-block'; termBtn.disabled = false; termBtn.setAttribute('data-job-id', data.job_id); }
    if (preEl) preEl.textContent = 'Waiting for logs...\\n';
    if (logsContainer) logsContainer.style.display = 'flex';
    _runOffsets[data.job_id] = 0;
    _activeRuns++;
    pollRerunStatus(btn, key, data.job_id, statusEl, termBtn, null, preEl, logsContainer, onComplete);
  } catch (err) {
    btn.disabled = false; btn.textContent = orig;
    if (statusEl) statusEl.textContent = 'Server offline';
    if (typeof onComplete === 'function') onComplete();
  }
}
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

def _device_summary(rows: list[RunEntry]) -> list[dict]:
    """Per-device aggregate: counts + last run time. Sorted by most-recent activity."""
    by_dev: dict[str, dict] = {}
    for r in rows:
        d = by_dev.setdefault(r.device, {"device": r.device, "PASS": 0, "FAIL": 0, "SKIP": 0, "UNKNOWN": 0, "last": r.when})
        d[r.status if r.status in ("PASS", "FAIL", "SKIP") else "UNKNOWN"] += 1
        if r.when > d["last"]:
            d["last"] = r.when
    return sorted(by_dev.values(), key=lambda d: d["last"], reverse=True)


def _append_date_group(html: list[str], date_str: str, rows: list[RunEntry], today_str: str) -> None:
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
        href_js = _js_arg(r.report_href)
        stem_js = _js_arg(r.stem)
        folder_js = _js_arg(r.folder)
        time_str = r.when.strftime("%H:%M:%S")
        dev_id = escape(r.device, quote=True)
        html.append(f'<li class="run-item" data-status="{status_cls}" data-name="{escape(r.stem.lower(), quote=True)}" data-device="{dev_id}">')
        html.append('<div class="run-main">')
        html.append(f'<span class="badge {status_cls}">{escape(r.status)}</span>')
        html.append(f'<a class="run-name" href="{href}" onclick="openReport(event, \'{href_js}\', \'{stem_js}\')">{stem}</a>')
        html.append('</div>')
        html.append('<div class="run-meta">')
        html.append(f'<span class="dev-tag" title="Device">&#128241; {escape(r.device)}</span>')
        html.append(f'<span class="run-time">{time_str}</span>')
        html.append(f'<button class="rerun-btn" data-folder="{folder}" onclick="rerunTest(this, \'{folder_js}\')" title="Rerun this test">↺ Rerun</button>')
        html.append(f'<button class="terminate-btn" data-folder="{folder}" onclick="terminateTest(this, \'{folder_js}\')" title="Terminate this test">⏹ Terminate</button>')
        html.append(f'<button class="logs-btn" data-folder="{folder}" onclick="toggleLogs(\'{folder_js}\')" title="Toggle CLI Logs">📄 Logs</button>')
        html.append(f'<span class="rerun-status" data-folder="{folder}"></span>')
        html.append(f'<button class="delete-btn" title="Delete Report" onclick="deleteRun(event, \'{folder_js}\')">')
        html.append('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>')
        html.append('</button>')
        html.append('</div>')
        html.append('</li>')
        html.append(f'<li class="run-logs-container" id="logs-{folder}"><pre id="pre-{folder}"></pre></li>')
    html.append('</ul></div></details>')


def _append_catalog(html: list[str], catalog: list[tuple[str, list[dict]]]) -> None:
    if not catalog:
        html.append('<p class="empty-state">No test root found (../Test missing).</p>')
        return
    idx = 0
    for suite, tests in catalog:
        html.append('<details open class="suite-group">')
        html.append(f'<summary class="suite-summary" style="display: flex; align-items: center;">')
        html.append(f'<span style="flex: 1;"><span>{escape(suite)}</span> &mdash; {len(tests)} tests</span>')
        html.append(f'<button class="rerun-btn run-all-btn" onclick="runAllTests(this)" title="Run all tests in {escape(suite)}" style="margin-right: 16px;">▶ Run All</button>')
        html.append('</summary>')
        html.append('<div class="group-content"><ul>')
        for t in tests:
            key = f"cat{idx}"
            idx += 1
            stem = escape(t["stem"])
            air = escape(t["air_path"], quote=True)
            stem_js = _js_arg(t["stem"])
            air_js = _js_arg(t["air_path"])
            status = t["last_status"]
            status_cls = status.lower() if status in {"PASS", "FAIL", "SKIP"} else "unknown"
            badge = escape(status) if status else "never run"
            html.append('<li class="run-item">')
            html.append('<div class="run-main">')
            html.append(f'<span class="badge {status_cls}">{badge}</span>')
            if t["last_href"]:
                href = escape(t["last_href"], quote=True)
                href_js = _js_arg(t["last_href"])
                html.append(f'<a class="run-name" href="{href}" onclick="openReport(event, \'{href_js}\', \'{stem_js}\')">{stem}</a>')
            else:
                html.append(f'<span class="run-name">{stem}</span>')
            html.append('</div>')
            html.append('<div class="run-meta">')
            html.append(f'<button class="rerun-btn" onclick="runCatalogTest(this, \'{key}\', \'{air_js}\')" title="Run this test">▶ Run</button>')
            html.append(f'<button class="terminate-btn" id="cat-term-{key}" data-folder="{key}" onclick="terminateTest(this, \'{key}\')" style="display:none">⏹ Terminate</button>')
            html.append(f'<button class="logs-btn" onclick="toggleLogs(\'{key}\')" title="Toggle CLI Logs">📄 Logs</button>')
            html.append(f'<span class="rerun-status" id="cat-status-{key}"></span>')
            html.append('</div>')
            html.append('</li>')
            html.append(f'<li class="run-logs-container" id="logs-{key}"><pre id="pre-{key}"></pre></li>')
        html.append('</ul></div></details>')


def render_html(
    suite_groups: list[tuple[str, list[tuple[str, list[RunEntry]]]]],
    catalog: list[tuple[str, list[dict]]] | None = None,
) -> str:
    today_str = date.today().strftime("%Y-%m-%d")
    html = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>Dagster Test Reports</title>',
        f'<style>{THEME_CSS}\n{_CSS}</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        '<h1>Dagster Test Reports</h1>',
        '<div id="banner" style="display:none; background:rgba(239,68,68,0.15); border:1px solid var(--fail); color:var(--fail); padding:12px; border-radius:8px; margin-bottom:16px; font-size:14px;"></div>',
        '<div class="tabs">',
        '<button class="tab-btn active" data-tab="report" onclick="showTab(\'report\')">Report</button>',
        '<button class="tab-btn" data-tab="catalog" onclick="showTab(\'catalog\')">Test Catalog</button>',
        '</div>',
        '<div id="tab-report" class="tab-pane active">',
    ]

    if not suite_groups:
        html.append('<p class="empty-state">No test runs found. Generate some reports to see them here!</p>')
    else:
        all_rows = [r for _, dgs in suite_groups for _, rows in dgs for r in rows]
        n_pass = sum(1 for r in all_rows if r.status == "PASS")
        n_fail = sum(1 for r in all_rows if r.status == "FAIL")
        denom = n_pass + n_fail
        pass_rate = f"{round(100 * n_pass / denom)}%" if denom else "&mdash;"
        html.append('<div class="summary-bar">')
        html.append(f'<div class="metric"><div class="label">Runs</div><div class="value">{len(all_rows)}</div></div>')
        html.append(f'<div class="metric"><div class="label">Passed</div><div class="value pass">{n_pass}</div></div>')
        html.append(f'<div class="metric"><div class="label">Failed</div><div class="value fail">{n_fail}</div></div>')
        html.append(f'<div class="metric"><div class="label">Pass rate</div><div class="value">{pass_rate}</div></div>')
        html.append('</div>')

        devices = _device_summary(all_rows)
        html.append('<div class="device-bar">')
        for d in devices:
            dev_id = escape(d["device"], quote=True)
            last_str = d["last"].strftime("%Y-%m-%d %H:%M:%S")
            html.append(f'<div class="device-card" data-device="{dev_id}" onclick="toggleDevice(this)" title="Filter by this device">')
            html.append(f'<div class="dev-id">&#128241; {escape(d["device"])}</div>')
            html.append('<div class="dev-counts">')
            html.append(f'<span class="p">&#10003; {d["PASS"]}</span>')
            html.append(f'<span class="f">&#10007; {d["FAIL"]}</span>')
            if d["SKIP"]:
                html.append(f'<span class="s">&#8722; {d["SKIP"]}</span>')
            html.append('</div>')
            html.append(f'<div class="dev-last">Last run: {escape(last_str)}</div>')
            html.append('</div>')
        html.append('</div>')

        html.append('<div class="controls">')
        html.append('<input type="text" id="dash-search" placeholder="Filter by test name…">')
        html.append('<button class="filter-pill active" data-status="all">All</button>')
        html.append('<button class="filter-pill" data-status="pass">Pass</button>')
        html.append('<button class="filter-pill" data-status="fail">Fail</button>')
        html.append('<button class="filter-pill" data-status="skip">Skip</button>')
        html.append('</div>')

        for suite, date_groups in suite_groups:
            html.append('<details open class="suite-group">')
            html.append(f'<summary class="suite-summary"><span>{escape(suite)}</span></summary>')
            html.append('<div class="suite-content">')
            for date_str, rows in date_groups:
                _append_date_group(html, date_str, rows, today_str)
            html.append('</div></details>')

    html.append('</div>')  # end tab-report
    html.append('<div id="tab-catalog" class="tab-pane">')
    _append_catalog(html, catalog or [])
    html.append('</div>')  # end tab-catalog

    html.append('</div>') # end container

    # Modal HTML
    html.append('<div id="modal"><div id="modal-bg"></div><div id="modal-panel">')
    html.append('<div id="modal-bar"><div id="modal-title"></div><button id="modal-close">x</button></div>')
    html.append('<iframe id="modal-frame"></iframe></div></div>')
    
    html.append(f'<script>{_JS}</script>')
    html.append('</body></html>')
    return "\n".join(html)

def regenerate_global_report(report_root: Path, test_root: Path | None = None) -> Path:
    report_root.mkdir(parents=True, exist_ok=True)
    if test_root is None:
        test_root = Path(__file__).resolve().parent.parent.parent / "Test"
    entries = scan_runs(report_root)
    suite_groups = group_by_suite_then_date(entries)
    catalog = build_catalog(test_root, entries)
    html = render_html(suite_groups, catalog=catalog)
    out = report_root / "report.html"
    # Atomic write: unique temp + os.replace so concurrent regens (page load +
    # auto-refresh polls under ThreadingHTTPServer) never serve a torn file.
    tmp = report_root / f".report.{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(html, encoding="utf-8")
        os.replace(tmp, out)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return out


if __name__ == '__main__':
    regenerate_global_report(Path(__file__).parent.parent / 'report_run')
