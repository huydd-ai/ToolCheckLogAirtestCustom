import html as _html
import sys
from datetime import datetime
from pathlib import Path


def write_log_txt(out_dir: Path, tc_name: str, steps: list[dict], error_top: Exception | None) -> None:
    """Write structured log.txt from captured steps."""
    log_file = out_dir / "log.txt"
    overall_status = "FAIL" if error_top or any(s["status"] == "FAIL" for s in steps) else "PASS"
    lines = [
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


def _normalize_and_filter_airtest_log(log_path: Path, mode: str) -> None:
    """Promote NDJSON entry depths and optionally filter noisy logs for dev mode."""
    import json
    if not log_path.exists():
        return
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        depths: list[int] = []
        
        # Pass 1: find error indices
        error_indices = set()
        for i, ln in enumerate(raw_lines):
            try:
                obj = json.loads(ln)
                if obj.get("data", {}).get("traceback") is not None:
                    error_indices.add(i)
            except json.JSONDecodeError:
                pass
        
        pending_screen = None
        for i, ln in enumerate(raw_lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
                data_dict = obj.get("data", {})
                tag = obj.get("tag")
                
                # Intercept annotated error screenshots
                if data_dict.get("name") == "Take Screen and Log":
                    data_dict["name"] = "try_log_screen"
                    data_dict["call_args"] = {"screen": None, "quality": None, "max_size": None}
                    data_dict["start_time"] = obj["time"]
                    data_dict["end_time"] = obj["time"]
                    pending_screen = obj
                    
                    # Redraw the point in the middle of the screen
                    fname = data_dict.get("ret", {}).get("screen")
                    if fname:
                        img_path = log_path.parent / fname
                        if img_path.exists():
                            try:
                                import cv2
                                import numpy as np
                                img = cv2.imread(str(img_path))
                                if img is not None:
                                    # Erase existing red circle
                                    red_mask = ((img[:,:,2] > 150) & (img[:,:,1] < 50) & (img[:,:,0] < 50)).astype(np.uint8) * 255
                                    red_mask = cv2.dilate(red_mask, np.ones((3,3), np.uint8), iterations=1)
                                    img = cv2.inpaint(img, red_mask, 3, cv2.INPAINT_TELEA)
                                    # Draw new circle in the middle
                                    h, w = img.shape[:2]
                                    cv2.circle(img, (w//2, h//2), 30, (0, 0, 255), 3)
                                    cv2.circle(img, (w//2, h//2), 5, (0, 0, 255), -1)
                                    cv2.imwrite(str(img_path), img)
                            except Exception:
                                pass
                    continue

                # Dev mode filters out game step noise
                if mode == "dev":
                    has_error = data_dict.get("traceback") is not None
                    if tag == "function" and not has_error:
                        # Keep if it is near an error to preserve crash screenshots
                        if not any(e in error_indices for e in range(i-2, i+5)):
                            continue
                            
                entries.append(obj)
                d = obj.get("depth")
                if isinstance(d, int):
                    depths.append(d)
                    
                # If we just appended an error log, append the pending annotated screen as its child
                if pending_screen and data_dict.get("traceback") is not None:
                    entries.append(pending_screen)
                    depths.append(pending_screen.get("depth", 2))
                    pending_screen = None
                    
            except json.JSONDecodeError:
                continue
                
        if pending_screen:
            entries.append(pending_screen)
            depths.append(pending_screen.get("depth", 2))
                
        if not depths:
            log_path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in entries) + "\n", encoding="utf-8")
            return
            
        offset = min(depths) - 1
        for obj in entries:
            d = obj.get("depth")
            if isinstance(d, int) and offset > 0:
                obj["depth"] = d - offset
                
        log_path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in entries) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[WARN] log normalization/filtering failed: {e}", file=sys.stderr)


def generate_html(air_path: Path, out_dir: Path, mode: str, ndjson_name: str = "airtest.log", recordings: list[Path] | None = None, status: str = "PASS") -> None:
    """Generate Airtest HTML report from NDJSON log."""
    from airtest.report.report import LogToHtml

    _normalize_and_filter_airtest_log(out_dir / ndjson_name, mode)

    rel_recordings = [r.name for r in (recordings or []) if r.exists()]

    log_to_html = LogToHtml(
        script_root=str(air_path),
        log_root=str(out_dir),
        logfile=ndjson_name,
        export_dir=str(out_dir),
        lang="en",
    )
    log_to_html.report(output_file="report.html", record_list=rel_recordings)

    exported = out_dir / f"{air_path.stem}.log"
    target_report = exported / "report.html"
    if not target_report.exists():
        target_report = exported / "log.html"
    if target_report.exists():
        html_content = target_report.read_text(encoding="utf-8")
        
        # Override Airtest's native success indicator if the overall test failed
        if status == "FAIL" and '"test_result": true' in html_content:
            html_content = html_content.replace('"test_result": true', '"test_result": false')
        
        # Fix Airtest's absolute static path bug (e.g. href="C:/.../static/css/..." -> href="static/css/...")
        import re
        html_content = re.sub(r'(href|src)="[^"]*?(static/(?:css|js)/[^"]*?)"', r'\1="\2"', html_content)
        
        # Fix Airtest's double-slash static path bug (static//css -> static/css)
        if "static//" in html_content:
            html_content = html_content.replace("static//", "static/")
            
        target_report.write_text(html_content, encoding="utf-8")

        redirect_rel = f"{exported.name}/{target_report.name}"
        (out_dir / "report.html").write_text(
            "<!DOCTYPE html><meta charset=\"utf-8\">"
            f"<meta http-equiv=\"refresh\" content=\"0; url={redirect_rel}\">"
            "<title>Redirecting...</title>"
            f"<p>If you are not redirected, <a href=\"{redirect_rel}\">click here</a>.</p>",
            encoding="utf-8",
        )


_VALID_STEP_STATUSES = {"PASS", "FAIL"}


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
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,Segoe UI,Roboto,sans-serif;min-height:100vh;padding:0}}
.banner{{padding:28px 32px 20px;text-align:center}}
.banner.pass{{background:#0f2d1a;border-bottom:2px solid #2ea043}}
.banner.fail{{background:#2d0f0f;border-bottom:2px solid #da3633}}
.banner.skip{{background:#2d2d0f;border-bottom:2px solid #d29922}}
.banner .status{{font-size:48px;font-weight:800;letter-spacing:2px}}
.banner .status.pass{{color:#56d364}}
.banner .status.fail{{color:#ff7b72}}
.banner .status.skip{{color:#d29922}}
.banner .meta{{margin-top:8px;font-size:14px;color:#8b949e}}
.banner .meta span{{margin:0 12px}}
.banner .rec-badge{{display:inline-block;background:#1c2128;padding:3px 10px;border-radius:10px;font-size:12px;color:#58a6ff;text-decoration:none;margin:8px 4px 0}}
.banner .rec-badge:hover{{background:#30363d}}
.stats{{display:flex;gap:16px;justify-content:center;padding:20px 32px;background:#161b22;border-bottom:1px solid #30363d;flex-wrap:wrap}}
.stat-box{{text-align:center;min-width:80px}}
.stat-box .num{{font-size:24px;font-weight:700}}
.stat-box .num.pass{{color:#56d364}}
.stat-box .num.fail{{color:#ff7b72}}
.stat-box .label{{font-size:11px;color:#6e7681;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}}
.filters{{padding:12px 32px;display:flex;gap:8px;align-items:center;background:#161b22;border-bottom:1px solid #30363d;flex-wrap:wrap}}
.filters button{{padding:4px 14px;border:1px solid #30363d;border-radius:6px;background:#1c2128;color:#c9d1d9;cursor:pointer;font-size:12px}}
.filters button:hover{{background:#30363d}}
.filters button.active{{background:#388bfd;border-color:#388bfd;color:#fff}}
.filters input{{flex:1;min-width:180px;padding:5px 10px;border:1px solid #30363d;border-radius:6px;background:#0d1117;color:#c9d1d9;font-size:13px;outline:none}}
.filters input:focus{{border-color:#58a6ff}}
table{{width:100%;border-collapse:collapse}}
th{{background:#161b22;padding:8px 12px;text-align:left;font-size:11px;color:#6e7681;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid #30363d;position:sticky;top:0}}
td{{padding:8px 12px;border-bottom:1px solid #21262d;font-size:13px;vertical-align:middle}}
tr.pass{{background:transparent}}
tr.fail{{background:#2d0f0f33}}
tr.fail:hover{{background:#2d0f0f66}}
tr.pass:hover{{background:#1c2128}}
.status-badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;min-width:44px;text-align:center}}
.status-badge.pass{{background:#0f2d1a;color:#56d364;border:1px solid #2ea04333}}
.status-badge.fail{{background:#2d0f0f;color:#ff7b72;border:1px solid #da363333}}
td .screenshot{{max-width:72px;max-height:54px;border-radius:4px;border:1px solid #30363d;cursor:pointer;vertical-align:middle}}
td .error-text{{color:#ff7b72;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}}
.no-runs{{text-align:center;padding:40px;color:#6e7681;font-style:italic}}
.error-panel{{background:#161b22;border-top:1px solid #30363d;border-bottom:1px solid #30363d;padding:20px 32px}}
.error-panel h2{{font-size:14px;color:#ff7b72;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}}
.error-panel pre{{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;color:#ff7b72;font-size:12px;white-space:pre-wrap;word-break:break-word;margin-bottom:12px}}
.error-panel img{{max-width:100%;border-radius:6px;border:1px solid #30363d}}
.modal{{display:none;position:fixed;inset:0;z-index:100;align-items:center;justify-content:center}}
.modal-bg{{position:fixed;inset:0;background:rgba(0,0,0,.8)}}
.modal-content{{position:relative;z-index:101;max-width:90%;max-height:90%}}
.modal-content img{{max-width:100%;max-height:85vh;border-radius:8px;border:1px solid #30363d}}
.modal-close{{position:absolute;top:-32px;right:0;background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer}}
.modal-close:hover{{color:#f0f6fc}}
</style></head><body>
<div class="banner {status_cls}">
  <div class="status {status_cls}">{safe_status}</div>
  <div class="meta"><span>{safe_tc_name}</span><span>|</span><span>{total} steps</span>""")

    for rec in recordings:
        safe_rec = _html.escape(rec.name, quote=True)
        parts.append(f'<br><a class="rec-badge" href="{safe_rec}">&#9654; {safe_rec}</a>')

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

    out = out_dir / "report_summary.html"
    out.write_text("".join(parts), encoding="utf-8")
    return out
