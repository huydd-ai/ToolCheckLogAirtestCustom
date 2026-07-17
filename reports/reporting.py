import html as _html
import json as _json
from datetime import datetime
from pathlib import Path

# Airtest NDJSON tag -> log level shown in the dev view.
_TAG_LEVEL = {"function": "INFO", "info": "INFO", "warning": "WARNING", "error": "ERROR"}


def _fmt_secs(secs: float) -> str:
    """Format seconds as compact human duration: '4.21s', '1m 04s', '1h 02m 03s'."""
    if secs < 60:
        return f"{secs:.2f}s"
    s = int(round(secs))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s"


def _parse_airtest_log(text: str) -> list[dict]:
    """Parse Airtest's NDJSON log into command rows: one row per logged action.

    Each line is a JSON object with `tag`, `time`, and a `data` payload holding the
    command `name`, `call_args`, timing, and (on failure) a `traceback`.
    """
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        data = obj.get("data") or {}
        tag = str(obj.get("tag") or "")
        name = data.get("name") or data.get("log") or tag or "(unnamed)"
        tb = data.get("traceback")

        screen = data.get("screen")
        if not screen and isinstance(data.get("ret"), dict):
            screen = data["ret"].get("screen")
        if isinstance(screen, dict):
            screen = screen.get("screen")
        img = screen if isinstance(screen, str) and screen else None

        ts = obj.get("time") or data.get("start_time")
        try:
            time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else ""
        except (OSError, ValueError, OverflowError):
            time_str = ""

        if tb:
            level = "ERROR"
            tb_lines = str(tb).strip().splitlines()
            msg = tb_lines[-1] if tb_lines else str(name)
        else:
            level = _TAG_LEVEL.get(tag.lower(), "INFO")
            msg = str(name)
            args = data.get("call_args")
            if args:
                try:
                    msg += " " + _json.dumps(args, default=str, ensure_ascii=False)
                except (TypeError, ValueError):
                    pass
            st, en = data.get("start_time"), data.get("end_time")
            if isinstance(st, (int, float)) and isinstance(en, (int, float)) and en >= st and "(" not in str(name):
                msg += f"  ({en - st:.2f}s)"

        rows.append({"time": time_str, "level": level, "src": tag or "airtest", "msg": msg, "img": img})
    return rows

try:
    from dagster.reports.report_theme import THEME_CSS
except ModuleNotFoundError:
    from report_theme import THEME_CSS


def write_log_txt(
    out_dir: Path,
    tc_name: str,
    steps: list[dict],
    error_top: Exception | None,
    air_path: Path | None = None,
    device_id: str | None = None,
) -> None:
    """Write structured log.txt from captured steps."""
    log_file = out_dir / "log.txt"
    overall_status = "FAIL" if error_top or any(s["status"] == "FAIL" for s in steps) else "PASS"
    lines = []
    if air_path is not None:
        lines.append(f"AIR_PATH={air_path.resolve()}")
    if device_id:
        lines.append(f"DEVICE={device_id}")
    lines += [
        f"# {tc_name}",
        f"# Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Status: {overall_status}",
        "",
    ]
    for step in steps:
        screenshot = step["screenshot"] or "-"
        clean_name = step['name'].strip()
        if step["status"] == "INFO":
            base_line = f"{clean_name}: {screenshot}, {step['status']}"
        else:
            base_line = f"{clean_name}: {step['action']}, {screenshot}, {step['status']}"
        
        if step["behaviour"]:
            lines.append(f"{base_line}, {step['behaviour']}")
        else:
            lines.append(base_line)
    if error_top and not steps:
        lines.append(f"ERROR: {str(error_top)}")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


_VALID_STEP_STATUSES = {"PASS", "FAIL", "INFO"}

# Per-run report CSS. Plain string (single braces) so it injects cleanly into the
# head f-string below. Colors come from THEME_CSS :root vars — shared with the dashboard.
_REPORT_CSS = """
*{margin:0;padding:0}
body{min-height:100vh;padding:0}
.banner{padding:20px 32px;display:flex;align-items:center;justify-content:center;gap:28px;flex-wrap:wrap}
.banner-info{text-align:center}
.banner-video{flex:0 0 auto}
.banner-video video{max-height:400px;max-width:720px;border-radius:8px;border:1px solid var(--border);background:#000;display:block}
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
.view-toggle{margin-top:12px;display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.view-toggle button{padding:5px 18px;border:none;background:var(--bg-item);color:var(--text-main);cursor:pointer;font-size:12px;font-weight:600}
.view-toggle button+button{border-left:1px solid var(--border)}
.view-toggle button:hover{background:var(--border)}
.view-toggle button.active{background:var(--accent);color:#fff}
.dev-log{display:none}
.lvl{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;min-width:58px;text-align:center;border:1px solid var(--border);color:var(--text-dim)}
.lvl.error,.lvl.critical{background:rgba(239,68,68,.15);color:var(--fail);border-color:rgba(239,68,68,.3)}
.lvl.warning{background:rgba(245,158,11,.15);color:#f59e0b;border-color:rgba(245,158,11,.3)}
.lvl.info{background:rgba(16,185,129,.12);color:var(--pass)}
#dev-table td.msg{font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word}
#dev-table tr[data-src="info"] td.msg{font-weight:700;font-size:14px;color:var(--accent)}
.dev-pager{display:flex;align-items:center;justify-content:center;gap:16px;padding:14px 32px}
.dev-pager button{padding:5px 14px;border:1px solid var(--border);border-radius:6px;background:var(--bg-item);color:var(--text-main);cursor:pointer;font-size:13px}
.dev-pager button:hover:not(:disabled){background:var(--border)}
.dev-pager button:disabled{opacity:.4;cursor:not-allowed}
#dev-page-info{font-size:13px;color:var(--text-dim);min-width:120px;text-align:center}
#dev-table td.time{color:var(--text-dim);white-space:nowrap;font-size:12px}
#dev-table td.src{color:var(--text-dim);font-size:12px;white-space:nowrap}
body.dev-view .tester-only{display:none}
body.dev-view .dev-log{display:block}
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
tr.info{background:transparent}
tr.info:hover{background:rgba(59,130,246,.05)}
tr.pass:hover{background:var(--bg-item)}
.status-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;min-width:44px;text-align:center}
.status-badge.pass{background:rgba(16,185,129,.15);color:var(--pass);border:1px solid rgba(16,185,129,.3)}
.status-badge.fail{background:rgba(239,68,68,.15);color:var(--fail);border:1px solid rgba(239,68,68,.3)}
.status-badge.info{background:rgba(59,130,246,.15);color:#3b82f6;border:1px solid rgba(59,130,246,.3)}
td .screenshot{max-width:72px;max-height:54px;border-radius:4px;border:1px solid var(--border);cursor:pointer;vertical-align:middle}
td .error-text{color:var(--fail);font-size:12px;max-width:400px;white-space:pre-wrap;word-break:break-word;cursor:pointer}
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
    airtest_log: str | None = None,
    elapsed: float | None = None,
) -> Path:
    status_cls = {"PASS": "pass", "FAIL": "fail"}.get(status, "skip")
    safe_status = _html.escape(status)
    safe_tc_name = _html.escape(tc_name)
    passed = sum(1 for s in steps if s["status"] == "PASS")
    failed = sum(1 for s in steps if s["status"] == "FAIL")
    total = passed + failed
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

    # Primary screen recording: prefer the raw capture over the step-highlights clip.
    primary_rec = next((r for r in recordings if "_steps" not in r.stem), recordings[0] if recordings else None)

    parts: list[str] = []

    parts.append(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_tc_name} — {safe_status}</title>
<style>
{THEME_CSS}
{_REPORT_CSS}
</style></head><body>
<div class="banner {status_cls}">
  <div class="banner-info">
  <div class="status {status_cls}">{safe_status}</div>
  <div class="meta"><span>{safe_tc_name}</span><span>|</span><span>{total} steps</span>{f'<span>|</span><span>&#9201; {_fmt_secs(elapsed)}</span>' if elapsed is not None else ''}""")

    for rec in recordings:
        safe_rec = _html.escape(rec.name, quote=True)
        label = "Step Highlights" if "_steps" in rec.stem else safe_rec
        parts.append(f'<br><a class="rec-badge" href="{safe_rec}">&#9654; {label}</a>')

    if airtest_log is not None:
        parts.append("""<div class="view-toggle">
  <button class="active" data-view="tester">Tester</button>
  <button data-view="dev">Dev</button>
</div>""")

    parts.append("""</div></div>""")  # /.meta /.banner-info

    if primary_rec is not None:
        safe_v = _html.escape(primary_rec.name, quote=True)
        parts.append(f'<div class="banner-video"><video src="{safe_v}" autoplay muted loop playsinline controls></video></div>')

    parts.append("""</div>""")  # /.banner

    parts.append('<div class="tester-only">')

    parts.append(f"""<div class="stats">
  <div class="stat-box"><div class="num">{total}</div><div class="label">Steps</div></div>
  <div class="stat-box"><div class="num pass">{passed}</div><div class="label">Passed</div></div>
  <div class="stat-box"><div class="num fail">{failed}</div><div class="label">Failed</div></div>
  <div class="stat-box"><div class="num">{total_duration:.2f}s</div><div class="label">Step Time</div></div>{f'<div class="stat-box"><div class="num">{_fmt_secs(elapsed)}</div><div class="label">Total Time</div></div>' if elapsed is not None else ''}
</div>""")

    parts.append("""<div class="filters">
  <button class="active" data-filter="all">All</button>
  <button data-filter="pass">Pass</button>
  <button data-filter="fail">Fail</button>
  <input type="text" id="search" placeholder="Search steps...">
</div>""")

    parts.append("""<table id="step-table">
<thead><tr><th>#</th><th>Step</th><th>Action</th><th>Status</th><th>Screenshot</th><th>Duration</th><th>Error</th></tr></thead><tbody>""")

    if len(steps) == 0:
        parts.append('<tr><td colspan="7" class="no-runs">No steps captured</td></tr>')
    else:
        step_idx = 1
        for s in steps:
            raw_status = s["status"] if s["status"] in _VALID_STEP_STATUSES else "FAIL"
            if raw_status == "PASS":
                row_cls = "pass"
            elif raw_status == "INFO":
                row_cls = "info"
            else:
                row_cls = "fail"
            
            safe_name = _html.escape(s["name"])
            safe_action = _html.escape(s["action"])
            safe_behaviour = _html.escape(s["behaviour"] or "")
            dur = s.get("duration") or 0
            dur_str = f"{dur:.2f}s"
            
            # For INFO milestones, omit step number, action, and duration.
            if raw_status == "INFO":
                idx_display = ""
                safe_action = ""
                dur_str = ""
                # Optionally make the text bolder
                safe_name = f"<strong>{safe_name}</strong>"
            else:
                idx_display = str(step_idx)
                step_idx += 1

            screenshot_html = ""
            if s.get("screenshot"):
                safe_src = _html.escape(s["screenshot"], quote=True)
                screenshot_html = f'<img class="screenshot" src="{safe_src}" onclick="openModal(this.src)" loading="lazy">'

            error_html = ""
            if safe_behaviour:
                error_html = f'<div class="error-text" title="{safe_behaviour}">{safe_behaviour}</div>'

            parts.append(f"""<tr class="{row_cls}" data-status="{row_cls}">
<td>{idx_display}</td>
<td class="step-name">{safe_name}</td>
<td>{safe_action}</td>
<td><span class="status-badge {row_cls}">{raw_status}</span></td>
<td>{screenshot_html}</td>
<td>{dur_str}</td>
<td>{error_html}</td>
</tr>""")

    parts.append("""</tbody></table>""")

    parts.append('</div>')  # /.tester-only

    if airtest_log is not None:
        log_rows = _parse_airtest_log(airtest_log)
        parts.append('<div class="dev-log">')
        parts.append("""<div class="filters">
  <button class="active" data-dev-filter="all">All</button>
  <button data-dev-filter="error">Error</button>
  <button data-dev-filter="warning">Warn</button>
  <button data-dev-filter="info">Info</button>
  <input type="text" id="dev-search" placeholder="Search commands...">
</div>""")
        parts.append("""<table id="dev-table">
<thead><tr><th>#</th><th>Time</th><th>Level</th><th>Source</th><th>Message</th><th>Image</th></tr></thead><tbody>""")
        if not log_rows:
            parts.append('<tr><td colspan="6" class="no-runs">No commands logged</td></tr>')
        else:
            for i, r in enumerate(log_rows, 1):
                lvl = r["level"]
                lvl_cls = lvl.lower()
                row_cls = "fail" if lvl in ("ERROR", "CRITICAL") else "pass"
                lvl_html = f'<span class="lvl {lvl_cls}">{_html.escape(lvl)}</span>' if lvl else ""
                img_html = ""
                if r.get("img"):
                    safe_img = _html.escape(r["img"], quote=True)
                    img_html = f'<img class="screenshot" src="{safe_img}" onclick="openModal(this.src)" loading="lazy">'
                parts.append(f"""<tr class="{row_cls}" data-level="{lvl_cls or 'none'}" data-src="{_html.escape(r["src"], quote=True)}">
<td>{i}</td>
<td class="time">{_html.escape(r["time"])}</td>
<td>{lvl_html}</td>
<td class="src">{_html.escape(r["src"])}</td>
<td class="msg">{_html.escape(r["msg"])}</td>
<td>{img_html}</td>
</tr>""")
        parts.append("""</tbody></table>""")
        parts.append("""<div class="dev-pager">
  <button id="dev-prev">&#8249; Prev</button>
  <span id="dev-page-info"></span>
  <button id="dev-next">Next &#8250;</button>
</div>""")
        parts.append("""</div>""")  # /.dev-log

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
var viewBtns=document.querySelectorAll('.view-toggle button');
viewBtns.forEach(function(b){b.addEventListener('click',function(){
  viewBtns.forEach(function(x){x.classList.remove('active')});
  this.classList.add('active');
  document.body.classList.toggle('dev-view',this.getAttribute('data-view')==='dev');
})});
var devBtns=document.querySelectorAll('[data-dev-filter]');
var devSearch=document.getElementById('dev-search');
var devRows=Array.prototype.slice.call(document.querySelectorAll('#dev-table tbody tr'));
var devPrev=document.getElementById('dev-prev');
var devNext=document.getElementById('dev-next');
var devInfo=document.getElementById('dev-page-info');
var DEV_PER_PAGE=10;
var devPage=1;
function devMatches(r){
  var active=document.querySelector('[data-dev-filter].active');
  var f=active?active.getAttribute('data-dev-filter'):'all';
  var q=devSearch?devSearch.value.toLowerCase():'';
  var lvl=r.getAttribute('data-level');
  if(f!=='all'){
    if(f==='error'){if(lvl!=='error'&&lvl!=='critical')return false;}
    else if(lvl!==f)return false;
  }
  if(q&&r.textContent.toLowerCase().indexOf(q)===-1)return false;
  return true;
}
function applyDevFilters(){
  var matches=[];
  devRows.forEach(function(r){
    if(devMatches(r))matches.push(r); else r.style.display='none';
  });
  var pages=Math.max(1,Math.ceil(matches.length/DEV_PER_PAGE));
  if(devPage>pages)devPage=pages;
  if(devPage<1)devPage=1;
  matches.forEach(function(r,i){
    var p=Math.floor(i/DEV_PER_PAGE)+1;
    r.style.display=(p===devPage)?'':'none';
  });
  if(devInfo)devInfo.textContent=matches.length+' rows · page '+devPage+'/'+pages;
  if(devPrev)devPrev.disabled=(devPage<=1);
  if(devNext)devNext.disabled=(devPage>=pages);
}
devBtns.forEach(function(b){b.addEventListener('click',function(){
  devBtns.forEach(function(x){x.classList.remove('active')});
  this.classList.add('active');
  devPage=1;
  applyDevFilters();
})});
if(devSearch)devSearch.addEventListener('input',function(){devPage=1;applyDevFilters();});
if(devPrev)devPrev.addEventListener('click',function(){devPage--;applyDevFilters();});
if(devNext)devNext.addEventListener('click',function(){devPage++;applyDevFilters();});
applyDevFilters();
function openModal(src){document.getElementById('modal-img').src=src;document.getElementById('modal').style.display='flex';}
function closeModal(){document.getElementById('modal').style.display='none';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
</script></body></html>""")

    out = out_dir / "report.html"
    out.write_text("".join(parts), encoding="utf-8")
    return out
