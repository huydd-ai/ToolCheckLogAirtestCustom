import html as _html
from datetime import datetime
from pathlib import Path

try:
    from dagster.report_theme import THEME_CSS
except ModuleNotFoundError:
    from report_theme import THEME_CSS


def write_log_txt(
    out_dir: Path,
    tc_name: str,
    steps: list[dict],
    error_top: Exception | None,
    air_path: Path | None = None,
) -> None:
    """Write structured log.txt from captured steps."""
    log_file = out_dir / "log.txt"
    overall_status = "FAIL" if error_top or any(s["status"] == "FAIL" for s in steps) else "PASS"
    lines = []
    if air_path is not None:
        lines.append(f"AIR_PATH={air_path.resolve()}")
    lines += [
        f"# {tc_name}",
        f"# Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Status: {overall_status}",
        "",
    ]
    for step in steps:
        screenshot = step["screenshot"] or "-"
        clean_name = step['name'].strip()
        base_line = f"{clean_name}: {step['action']}, {screenshot}, {step['status']}"
        if step["behaviour"]:
            lines.append(f"{base_line}, {step['behaviour']}")
        else:
            lines.append(base_line)
    if error_top and not steps:
        lines.append(f"ERROR: {str(error_top)}")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


_VALID_STEP_STATUSES = {"PASS", "FAIL"}

# Per-run report CSS. Plain string (single braces) so it injects cleanly into the
# head f-string below. Colors come from THEME_CSS :root vars — shared with the dashboard.
_REPORT_CSS = """
*{margin:0;padding:0}
body{min-height:100vh;padding:0}
.banner{padding:28px 32px 20px;text-align:center}
.banner.pass{background:rgba(16,185,129,.12);border-bottom:2px solid var(--pass)}
.banner.fail{background:rgba(239,68,68,.12);border-bottom:2px solid var(--fail)}
.banner.skip{background:rgba(100,116,139,.12);border-bottom:2px solid var(--skip)}
.banner .status{font-size:48px;font-weight:800;letter-spacing:2px}
.banner .status.pass{color:var(--pass)}
.banner .status.fail{color:var(--fail)}
.banner .status.skip{color:var(--skip)}
.banner .meta{margin-top:8px;font-size:14px;color:var(--text-dim)}
.banner .meta span{margin:0 12px}
.banner .rec-badge{display:inline-block;background:var(--bg-item);padding:3px 10px;border-radius:10px;font-size:12px;color:var(--accent);text-decoration:none;margin:8px 4px 0}
.banner .rec-badge:hover{background:var(--border)}
.stats{display:flex;gap:16px;justify-content:center;padding:20px 32px;background:var(--bg-card);border-bottom:1px solid var(--border);flex-wrap:wrap}
.stat-box{text-align:center;min-width:80px}
.stat-box .num{font-size:24px;font-weight:700}
.stat-box .num.pass{color:var(--pass)}
.stat-box .num.fail{color:var(--fail)}
.stat-box .label{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.05em;margin-top:2px}
.filters{padding:12px 32px;display:flex;gap:8px;align-items:center;background:var(--bg-card);border-bottom:1px solid var(--border);flex-wrap:wrap}
.filters button{padding:4px 14px;border:1px solid var(--border);border-radius:6px;background:var(--bg-item);color:var(--text-main);cursor:pointer;font-size:12px}
.filters button:hover{background:var(--border)}
.filters button.active{background:var(--accent);border-color:var(--accent);color:#fff}
.filters input{flex:1;min-width:180px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text-main);font-size:13px;outline:none}
.filters input:focus{border-color:var(--accent-hover)}
table{width:100%;border-collapse:collapse}
th{background:var(--bg-card);padding:8px 12px;text-align:left;font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--border);position:sticky;top:0}
td{padding:8px 12px;border-bottom:1px solid var(--bg-item);font-size:13px;vertical-align:middle}
tr.pass{background:transparent}
tr.fail{background:rgba(239,68,68,.07)}
tr.fail:hover{background:rgba(239,68,68,.13)}
tr.pass:hover{background:var(--bg-item)}
.status-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;min-width:44px;text-align:center}
.status-badge.pass{background:rgba(16,185,129,.15);color:var(--pass);border:1px solid rgba(16,185,129,.3)}
.status-badge.fail{background:rgba(239,68,68,.15);color:var(--fail);border:1px solid rgba(239,68,68,.3)}
td .screenshot{max-width:72px;max-height:54px;border-radius:4px;border:1px solid var(--border);cursor:pointer;vertical-align:middle}
td .error-text{color:var(--fail);font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.no-runs{text-align:center;padding:40px;color:var(--text-dim);font-style:italic}
.error-panel{background:var(--bg-card);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:20px 32px}
.error-panel h2{font-size:14px;color:var(--fail);text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.error-panel pre{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;color:var(--fail);font-size:12px;white-space:pre-wrap;word-break:break-word;margin-bottom:12px}
.error-panel img{max-width:100%;border-radius:6px;border:1px solid var(--border)}
.modal{display:none;position:fixed;inset:0;z-index:100;align-items:center;justify-content:center}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.8)}
.modal-content{position:relative;z-index:101;max-width:90%;max-height:90%}
.modal-content img{max-width:100%;max-height:85vh;border-radius:8px;border:1px solid var(--border)}
.modal-close{position:absolute;top:-32px;right:0;background:none;border:none;color:var(--text-dim);font-size:20px;cursor:pointer}
.modal-close:hover{color:#f0f6fc}
""".strip()


def generate_summary_report(
    out_dir: Path,
    tc_name: str,
    steps: list[dict],
    status: str,
    recordings: list[Path],
    error_top: Exception | None = None,
) -> Path:
    status_cls = {"PASS": "pass", "FAIL": "fail"}.get(status, "skip")
    safe_status = _html.escape(status)
    safe_tc_name = _html.escape(tc_name)
    total = len(steps)
    passed = sum(1 for s in steps if s["status"] == "PASS")
    failed = sum(1 for s in steps if s["status"] == "FAIL")
    total_duration = sum(s.get("duration") or 0 for s in steps)

    first_fail = next((s for s in steps if s["status"] == "FAIL"), None)
    error_message: str | None = None
    error_screenshot: str | None = None
    if error_top is not None:
        error_message = str(error_top)
    if first_fail is not None:
        if not error_message:
            error_message = first_fail.get("behaviour") or "Step failed (no detail)"
        error_screenshot = first_fail.get("screenshot")

    parts: list[str] = []

    parts.append(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_tc_name} — {safe_status}</title>
<style>
{THEME_CSS}
{_REPORT_CSS}
</style></head><body>
<div class="banner {status_cls}">
  <div class="status {status_cls}">{safe_status}</div>
  <div class="meta"><span>{safe_tc_name}</span><span>|</span><span>{total} steps</span>""")

    for rec in recordings:
        safe_rec = _html.escape(rec.name, quote=True)
        label = "Step Highlights" if "_steps" in rec.stem else safe_rec
        parts.append(f'<br><a class="rec-badge" href="{safe_rec}">&#9654; {label}</a>')

    parts.append("""</div></div>""")

    parts.append(f"""<div class="stats">
  <div class="stat-box"><div class="num">{total}</div><div class="label">Steps</div></div>
  <div class="stat-box"><div class="num pass">{passed}</div><div class="label">Passed</div></div>
  <div class="stat-box"><div class="num fail">{failed}</div><div class="label">Failed</div></div>
  <div class="stat-box"><div class="num">{total_duration:.2f}s</div><div class="label">Duration</div></div>
</div>""")

    parts.append("""<div class="filters">
  <button class="active" data-filter="all">All</button>
  <button data-filter="pass">Pass</button>
  <button data-filter="fail">Fail</button>
  <input type="text" id="search" placeholder="Search steps...">
</div>""")

    parts.append("""<table id="step-table">
<thead><tr><th>#</th><th>Step</th><th>Action</th><th>Status</th><th>Screenshot</th><th>Duration</th><th>Error</th></tr></thead><tbody>""")

    if total == 0:
        parts.append('<tr><td colspan="7" class="no-runs">No steps captured</td></tr>')
    else:
        for i, s in enumerate(steps, 1):
            raw_status = s["status"] if s["status"] in _VALID_STEP_STATUSES else "FAIL"
            row_cls = "pass" if raw_status == "PASS" else "fail"
            safe_name = _html.escape(s["name"])
            safe_action = _html.escape(s["action"])
            safe_behaviour = _html.escape(s["behaviour"] or "")
            dur = s.get("duration") or 0
            dur_str = f"{dur:.2f}s"

            screenshot_html = ""
            if s.get("screenshot"):
                safe_src = _html.escape(s["screenshot"], quote=True)
                screenshot_html = f'<img class="screenshot" src="{safe_src}" onclick="openModal(this.src)" loading="lazy">'

            error_html = ""
            if safe_behaviour:
                error_html = f'<div class="error-text" title="{safe_behaviour}">{safe_behaviour}</div>'

            parts.append(f"""<tr class="{row_cls}" data-status="{row_cls}">
<td>{i}</td>
<td class="step-name">{safe_name}</td>
<td>{safe_action}</td>
<td><span class="status-badge {row_cls}">{raw_status}</span></td>
<td>{screenshot_html}</td>
<td>{dur_str}</td>
<td>{error_html}</td>
</tr>""")

    parts.append("""</tbody></table>""")

    if error_message:
        safe_err = _html.escape(error_message)
        parts.append(f'<div class="error-panel"><h2>Failure detail</h2><pre>{safe_err}</pre>')
        if error_screenshot:
            safe_err_src = _html.escape(error_screenshot, quote=True)
            parts.append(f'<img src="{safe_err_src}" loading="lazy">')
        parts.append('</div>')

    parts.append("""<div class="modal" id="modal"><div class="modal-bg" onclick="closeModal()"></div><div class="modal-content"><button class="modal-close" onclick="closeModal()">✕</button><img id="modal-img"></div></div>
<script>
var filterBtns=document.querySelectorAll('.filters button');
var searchInput=document.getElementById('search');
var rows=document.querySelectorAll('#step-table tbody tr');
filterBtns.forEach(function(b){b.addEventListener('click',function(){
  filterBtns.forEach(function(x){x.classList.remove('active')});
  this.classList.add('active');
  applyFilters();
})});
searchInput.addEventListener('input',applyFilters);
function applyFilters(){
  var active=document.querySelector('.filters button.active');
  var filter=active?active.getAttribute('data-filter'):'all';
  var q=searchInput.value.toLowerCase();
  rows.forEach(function(r){
    var show=true;
    if(filter!=='all'&&r.getAttribute('data-status')!==filter)show=false;
    var nameCell=r.querySelector('.step-name');
    if(q&&(!nameCell||nameCell.textContent.toLowerCase().indexOf(q)===-1))show=false;
    r.style.display=show?'':'none';
  });
}
function openModal(src){document.getElementById('modal-img').src=src;document.getElementById('modal').style.display='flex';}
function closeModal(){document.getElementById('modal').style.display='none';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
</script></body></html>""")

    out = out_dir / "report.html"
    out.write_text("".join(parts), encoding="utf-8")
    return out
