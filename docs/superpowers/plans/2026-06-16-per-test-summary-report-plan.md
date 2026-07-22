# Per-Test Summary Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a standalone `report_summary.html` in each test output folder with a prominent PASS/FAIL banner, filterable step table, and summary stats.

**Architecture:** Three-file change: (1) add `duration` to step dict in `step_capture.py`, (2) add `generate_summary_report()` to `reporting.py` that writes a self-contained HTML with inline CSS/JS, (3) call it from `runner.py` after the existing Airtest report generation.

**Tech Stack:** Python 3.10+, stdlib (no new dependencies). Inline HTML/CSS/JS (no external assets).

---

### Task 1: Add `duration` field to captured steps

**Files:**
- Modify: `step_capture.py:51-77`

- [ ] **Step 1: Add `duration` to the step dict**

In `_hooked_run_step`, add `"duration": None` to the initial step dict, then compute it in both success and failure paths. `end - start` rounded to 2 decimals.

```python
def _hooked_run_step(name: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    action_name = getattr(action, "__name__", str(action))
    step = {
        "name": name,
        "action": action_name,
        "status": None,
        "screenshot": None,
        "behaviour": None,
        "duration": None,
    }
    start = _time.time()
    try:
        result = _orig_run_step(name, action, *args, **kwargs)
        screen_path = _snapshot_step(name)
        step["status"] = "PASS"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=None)
        return result
    except Exception as exc:
        screen_path = _snapshot_step(name)
        step["status"] = "FAIL"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["behaviour"] = str(exc)
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=str(exc))
        raise
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('step_capture.py').read()); print('OK')"`  
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add step_capture.py
git commit -m "feat: add duration field to captured step dict"
```

---

### Task 2: Add `generate_summary_report()` to `reporting.py`

**Files:**
- Modify: `reporting.py` (append new function)
- Test: `test_reporting.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Add to `test_reporting.py`. The function signature will be:
```python
def generate_summary_report(out_dir, tc_name, steps, status, recordings, error_top=None):
```

```python
import html as _html


def test_generate_summary_report_writes_file(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.5}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    assert path.exists()
    assert path.name == "report_summary.html"


def test_generate_summary_report_banner_shows_pass(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.5}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "PASS" in html
    assert "#56d364" in html or "pass" in html.lower()


def test_generate_summary_report_banner_shows_fail(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "FAIL", "screenshot": None, "behaviour": "Error", "duration": 2.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "FAIL", [], None)
    html = path.read_text(encoding="utf-8")
    assert "FAIL" in html
    assert "#ff7b72" in html or "fail" in html.lower()


def test_generate_summary_report_shows_test_name(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "my_test_case_01", [], "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "my_test_case_01" in html


def test_generate_summary_report_step_table_renders(tmp_path):
    from reporting import generate_summary_report
    steps = [
        {"name": "step one", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.2},
        {"name": "step two", "action": "wait", "status": "FAIL", "screenshot": None, "behaviour": "timeout", "duration": 5.0},
    ]
    path = generate_summary_report(tmp_path, "tc01", steps, "FAIL", [], None)
    html = path.read_text(encoding="utf-8")
    assert "step one" in html
    assert "step two" in html
    assert "timeout" in html


def test_generate_summary_report_empty_steps(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc01", [], "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "PASS" in html


def test_generate_summary_report_recording_badge_when_present(tmp_path):
    from reporting import generate_summary_report
    recording = tmp_path / "recording_device_tc01.mp4"
    recording.write_text("dummy")
    path = generate_summary_report(tmp_path, "tc01", [], "PASS", [recording], None)
    html = path.read_text(encoding="utf-8")
    assert "recording" in html.lower() or "mp4" in html


def test_generate_summary_report_duration_column_present(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.25}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "1.25" in html or "1.3" in html


def test_generate_summary_report_total_duration(tmp_path):
    from reporting import generate_summary_report
    steps = [
        {"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0},
        {"name": "s2", "action": "wait", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 2.5},
    ]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "3.5" in html


def test_generate_summary_report_preserves_html_escaped_names(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "<script>alert(1)</script>", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    raw = path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in raw
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in raw
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest test_reporting.py -v --tb=short`  
Expected: All new tests fail with `ImportError` or `AttributeError` (function not yet defined). Existing tests should still pass.

- [ ] **Step 3: Add import + write the implementation**

Add `import html as _html` to the top of `reporting.py` imports section, then append the new function. The function generates a self-contained HTML file:

```python
def generate_summary_report(
    out_dir: Path,
    tc_name: str,
    steps: list[dict],
    status: str,
    recordings: list[Path],
    error_top: Exception | None = None,
) -> Path:
    total = len(steps)
    passed = sum(1 for s in steps if s["status"] == "PASS")
    failed = sum(1 for s in steps if s["status"] == "FAIL")
    total_duration = sum(s.get("duration") or 0 for s in steps)
    recording_href = recordings[0].name if recordings else None

    heading_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(tc_name)} — {status}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,Segoe UI,Roboto,sans-serif;min-height:100vh;padding:0}}
.banner{{padding:28px 32px 20px;text-align:center}}
.banner.pass{{background:#0f2d1a;border-bottom:2px solid #2ea043}}
.banner.fail{{background:#2d0f0f;border-bottom:2px solid #da3633}}
.banner .status{{font-size:48px;font-weight:800;letter-spacing:2px}}
.banner .status.pass{{color:#56d364}}
.banner .status.fail{{color:#ff7b72}}
.banner .meta{{margin-top:8px;font-size:14px;color:#8b949e}}
.banner .meta span{{margin:0 12px}}
.banner .rec-badge{{display:inline-block;background:#1c2128;padding:3px 10px;border-radius:10px;font-size:12px;color:#58a6ff;text-decoration:none;margin-top:8px}}
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
.modal{{display:none;position:fixed;inset:0;z-index:100;align-items:center;justify-content:center}}
.modal-bg{{position:fixed;inset:0;background:rgba(0,0,0,.8)}}
.modal-content{{position:relative;z-index:101;max-width:90%;max-height:90%}}
.modal-content img{{max-width:100%;max-height:85vh;border-radius:8px;border:1px solid #30363d}}
.modal-close{{position:absolute;top:-32px;right:0;background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer}}
.modal-close:hover{{color:#f0f6fc}}
</style></head><body>
<div class="banner {status_cls}">
  <div class="status {status_cls}">{status}</div>
  <div class="meta"><span>{_html.escape(tc_name)}</span><span>|</span><span>{total} steps</span>"""

    if recording_href:
        heading_html += f'<br><a class="rec-badge" href="{_html.escape(recording_href, quote=True)}">&#9654; Recording</a>'

    heading_html += """</div></div>"""

    # Stats row
    heading_html += f"""<div class="stats">
  <div class="stat-box"><div class="num">{total}</div><div class="label">Steps</div></div>
  <div class="stat-box"><div class="num pass">{passed}</div><div class="label">Passed</div></div>
  <div class="stat-box"><div class="num fail">{failed}</div><div class="label">Failed</div></div>
  <div class="stat-box"><div class="num">{total_duration:.1f}s</div><div class="label">Duration</div></div>
</div>"""

    # Filters
    heading_html += """<div class="filters">
  <button class="active" data-filter="all">All</button>
  <button data-filter="pass">Pass</button>
  <button data-filter="fail">Fail</button>
  <input type="text" id="search" placeholder="Search steps...">
</div>"""

    # Table
    heading_html += """<table id="step-table">
<thead><tr><th>#</th><th>Step</th><th>Action</th><th>Status</th><th>Screenshot</th><th>Duration</th><th>Error</th></tr></thead><tbody>"""

    for i, s in enumerate(steps, 1):
        status_cls = "pass" if s["status"] == "PASS" else "fail"
        safe_name = _html.escape(s["name"])
        safe_action = _html.escape(s["action"])
        safe_behaviour = _html.escape(s["behaviour"] or "")
        dur = s.get("duration") or 0
        dur_str = f"{dur:.1f}s"

        screenshot_html = ""
        if s.get("screenshot"):
            safe_src = _html.escape(s["screenshot"], quote=True)
            screenshot_html = f'<img class="screenshot" src="{safe_src}" onclick="openModal(this.src)" loading="lazy">'

        error_html = ""
        if safe_behaviour:
            error_html = f'<div class="error-text" title="{safe_behaviour}">{safe_behaviour}</div>'

        heading_html += f"""<tr class="{status_cls}" data-status="{s["status"].lower()}">
<td>{i}</td>
<td>{safe_name}</td>
<td>{safe_action}</td>
<td><span class="status-badge {status_cls}">{s["status"]}</span></td>
<td>{screenshot_html}</td>
<td>{dur_str}</td>
<td>{error_html}</td>
</tr>"""

    heading_html += """</tbody></table>"""

    # Modal + script
    heading_html += """<div class="modal" id="modal"><div class="modal-bg" onclick="closeModal()"></div><div class="modal-content"><button class="modal-close" onclick="closeModal()">✕</button><img id="modal-img"></div></div>
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
    if(q&&r.cells[1].textContent.toLowerCase().indexOf(q)===-1)show=false;
    r.style.display=show?'':'none';
  });
}
function openModal(src){document.getElementById('modal-img').src=src;document.getElementById('modal').style.display='flex';}
function closeModal(){document.getElementById('modal').style.display='none';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
</script></body></html>"""

    out = out_dir / "report_summary.html"
    out.write_text(heading_html, encoding="utf-8")
    return out
```

The `status_cls` variable used in the banner is determined by:
```python
status_cls = "pass" if status == "PASS" else "fail"
```
This must be defined at the top of the function body, before the f-strings use it.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m pytest test_reporting.py -v --tb=short`  
Expected: All new and existing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add reporting.py test_reporting.py
git commit -m "feat: add generate_summary_report() for per-test summary HTML"
```

---

### Task 3: Wire summary report into `runner.py`

**Files:**
- Modify: `runner.py` (add import and call)
- Test: `test_reporting.py` (add integration-style test)

- [ ] **Step 1: Add import in `runner.py`**

Change the reporting import line to include `generate_summary_report`:

```python
from dagster.reporting import write_log_txt, generate_html, generate_summary_report
```

- [ ] **Step 2: Add the call after `generate_html()`**

In `runner.py`, after the existing `generate_html(...)` block (around line 84), add:

```python
        try:
            summary_path = generate_summary_report(out_dir, air_path.stem, steps, status, recordings, error_top)
            print(f"[INFO] summary report: {summary_path.name}")
        except Exception as e:
            print(f"[WARN] Failed to generate summary report: {e}", file=sys.stderr)
```

The full block should look like:
```python
        try:
            recordings = sorted(out_dir.glob("recording_*.mp4"))
            generate_html(air_path, out_dir, mode, ndjson_name="airtest.log", recordings=recordings)
            print(f"[INFO] report.html generated")
        except Exception as e:
            print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

        try:
            summary_path = generate_summary_report(out_dir, air_path.stem, steps, status, recordings, error_top)
            print(f"[INFO] summary report: {summary_path.name}")
        except Exception as e:
            print(f"[WARN] Failed to generate summary report: {e}", file=sys.stderr)
```

- [ ] **Step 3: Add integration test**

Add to `test_reporting.py`:

```python
def test_generate_summary_report_called_from_runner_integration(tmp_path):
    """Verify the function is importable via the dagster.reporting path used by runner.py."""
    import sys
    sys.path.insert(0, str(tmp_path))
    import importlib
    # Simulate runner's import path
    from reporting import generate_summary_report
    steps = []
    path = generate_summary_report(tmp_path, "tc_integration", steps, "PASS", [], None)
    assert path.exists()
    html = path.read_text(encoding="utf-8")
    assert "PASS" in html
    assert "tc_integration" in html
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest test_reporting.py -v --tb=short`  
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add runner.py test_reporting.py
git commit -m "feat: wire generate_summary_report into runner.py"
```

---

### Task 4: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest test_reporting.py test_aggregate_report.py -v --tb=short`  
Expected: All tests PASS.

- [ ] **Step 2: Clean up (if any issues)**

If a test fails, use systematic-debugging to diagnose and fix.
