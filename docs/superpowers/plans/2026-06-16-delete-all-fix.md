# Delete-All Button Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix "Delete all" button so report.html actually shows updated state after deleting runs.

**Architecture:** Two root causes: (1) `location.reload()` uses browser cache so old `report.html` is served even after server regenerates it. (2) Python's `SimpleHTTPRequestHandler` doesn't set `Cache-Control` headers, letting browsers cache the static HTML.

**Tech Stack:** Python http.server, vanilla JS

**Files:**
- Modify: `aggregate_report.py:159,170` (JS `_JS` string — change `location.reload()` to cache-busting redirect)
- Modify: `report_server.py:25-27` (add `send_header("Cache-Control", "no-cache")` to `__init__`)
- Test: `test_aggregate_report.py` (existing tests should still pass)

---

### Task 1: Fix browser caching in _JS

**Files:**
- Modify: `aggregate_report.py:159,170`

- [ ] **Step 1: Replace `location.reload()` with cache-busting redirect**

Change line 159 and 170 from:
```javascript
if(r.ok){location.reload();}
```
to:
```javascript
if(r.ok){window.location.href='report.html?_='+Date.now();}
```

This forces the browser to fetch `report.html` fresh from server instead of loading from cache.

- [ ] **Step 2: Regenerate script.js**

```bash
python -c "
import importlib, aggregate_report as ar
importlib.invalidate_caches()
importlib.reload(ar)
from pathlib import Path
ar.write_assets(Path('report_run'))
print('script.js regenerated')
"
```

- [ ] **Step 3: Run tests**

```bash
rtk pytest test_aggregate_report.py -v
```
Expected: 33 PASS

---

### Task 2: Disable server-side caching for HTML

**Files:**
- Modify: `report_server.py:25-27`

- [ ] **Step 1: Add no-cache header to `__init__`**

The server uses `SimpleHTTPRequestHandler` which inherits `send_head()`. Override to add `Cache-Control: no-cache` for `.html` responses.

Replace:
```python
class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_ROOT.resolve()), **kwargs)
```

With:
```python
class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_ROOT.resolve()), **kwargs)

    def send_head(self):
        path = self.translate_path(self.path)
        if path.endswith('.html') or path.endswith('.htm'):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        return super().send_head()
```

Wait — `send_head` must return the file-like object or `SimpleHTTPRequestHandler` will break. The parent `send_head()` returns a file-like object for static files. So the override must call parent and return its result.

Correct version:
```python
class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_ROOT.resolve()), **kwargs)

    def send_head(self):
        path = self.translate_path(self.path)
        if path.endswith('.html') or path.endswith('.htm'):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        return super().send_head()
```

- [ ] **Step 2: Verify server import still works**

```bash
python -c "import report_server; print('OK')"
```
Expected: OK

- [ ] **Step 3: Verify existing tests still pass**

```bash
rtk pytest test_aggregate_report.py -v
```
Expected: 33 PASS

---

### Task 3: Regenerate report and verify end-to-end

- [ ] **Step 1: Regenerate report.html + script.js**

```bash
python -B -c "
import importlib, aggregate_report as ar
importlib.invalidate_caches()
importlib.reload(ar)
from pathlib import Path
ar.regenerate_global_report(Path('report_run'))
print('report.html regenerated')
"
```

- [ ] **Step 2: Verify HTML has correct onclick attribute**

```bash
python -B -c "
html = open('report_run/report.html', encoding='utf-8').read()
print('onclick single quote:', \"onclick='deleteAllRuns\" in html)
print('cache busting:', '?._=' in html or 'Date.now()' in open('report_run/script.js').read())
"
```
Expected: both True

