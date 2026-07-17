# Dashboard UI Update, Error Fixes & Server Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all known defects (failing unit test, broken pytest collection, port double-bind, handler bugs, stuck UI job state), refactor `report_server.py` (dedupe job spawning, stop polluting `tests/`), and update the dashboard UI (error banner, live job logs, de-inlined styles, smarter polling).

**Architecture:** The repo is a custom Airtest runner (`dagster_run.py`) + a `ThreadingHTTPServer` dashboard (`report_server.py`) serving an Alpine.js/Chart.js frontend from `static/`. Data layer is `reports/report_data.py`. All changes stay inside `dagster/`; the host `../pixon/` and `../Test/` are never written.

**Tech Stack:** Python 3.10 stdlib (`http.server`, `subprocess`, `threading`), pytest, Alpine.js 3, Chart.js (vendored), plain CSS. No new dependencies.

## Global Constraints

- Windows-only environment; shell for verification is PowerShell, repo root is `D:\AutoRebase\dagster`.
- NO new pip dependencies. Stdlib + already-vendored JS only.
- Never write into `../pixon/` or `../Test/` (host repo property).
- `airtest.log` production/parsing must not be touched (used for FAIL detection in `runner.py`).
- All unit tests run with: `cd D:\AutoRebase\dagster; python -m pytest tests -q` (after Task 2 this collects cleanly).
- Frontend must keep working with the existing dark theme CSS variables in `static/styles.css`.
- Commit after every task (each task ends with a commit step).

---

### Task 1: Fix `test_compute_metrics` — remove chart-padding hack from data layer

The failing test: `compute_metrics()` in `reports/report_data.py:180-189` inserts a dummy "previous day" trend point when there is exactly 1 trend entry, so the Chart.js line chart can draw a line. That is presentation logic living in the data layer, and it breaks the test's `assert len(metrics["trend"]) == 1`. Move the padding to the frontend (Task 8 keeps chart behavior identical).

**Files:**
- Modify: `reports/report_data.py:180-189`
- Modify: `static/app.js:114-121` (renderChart)
- Test: `tests/test_report_data.py` (already exists, currently failing)

**Interfaces:**
- Produces: `compute_metrics(runs) -> dict` where `metrics["trend"]` contains ONLY real dates (no synthetic points). Frontend consumes `metrics.trend` and pads client-side.

- [ ] **Step 1: Run the failing test to confirm the failure**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_data.py::test_compute_metrics -v`
Expected: FAIL with `AssertionError: assert 2 == 1` (trend length).

- [ ] **Step 2: Delete the dummy-point block from `compute_metrics`**

In `reports/report_data.py`, delete exactly this block (lines 180-189):

```python
    # If there's only 1 point, add a dummy previous day so the line chart can draw a line
    if len(trend) == 1:
        from datetime import datetime, timedelta
        dt = datetime.strptime(trend[0]["date"], "%Y-%m-%d")
        prev_dt = dt - timedelta(days=1)
        trend.insert(0, {
            "date": prev_dt.strftime("%Y-%m-%d"),
            "total": 0,
            "pass_rate": trend[0]["pass_rate"]
        })
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_data.py -v`
Expected: 3 passed.

- [ ] **Step 4: Re-add the padding client-side in `renderChart()`**

In `static/app.js`, `renderChart()` currently starts:

```javascript
        renderChart() {
            if (!this.metrics || !this.metrics.trend) return;
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;
            
            const labels = this.metrics.trend.map(t => t.date);
            const passRates = this.metrics.trend.map(t => t.pass_rate);
            const totals = this.metrics.trend.map(t => t.total);
```

Replace those three `const` lines with:

```javascript
            // Pad a synthetic previous day when there is a single point so the
            // line chart can draw a line (presentation-only; API returns real dates).
            let trend = this.metrics.trend;
            if (trend.length === 1) {
                const d = new Date(trend[0].date + 'T00:00:00Z');
                d.setUTCDate(d.getUTCDate() - 1);
                const prev = d.toISOString().slice(0, 10);
                trend = [{ date: prev, total: 0, pass_rate: trend[0].pass_rate }, ...trend];
            }
            const labels = trend.map(t => t.date);
            const passRates = trend.map(t => t.pass_rate);
            const totals = trend.map(t => t.total);
```

- [ ] **Step 5: Verify chart still draws with one day of data**

Start the dev server (use the `report-server-preview` entry from `.claude/launch.json`, port 7171), open the dashboard, confirm the trend chart shows a line (two points) when only one date of runs exists, and no console errors.

- [ ] **Step 6: Commit**

```powershell
git add reports/report_data.py static/app.js
git commit -m "fix: keep compute_metrics trend pure, pad single-point chart client-side"
```

---

### Task 2: Fix pytest collection + stop `sync_tests` polluting `tests/`

`python -m pytest tests` collects 0 tests because the `sync_tests` daemon thread in `report_server.py:587-621` mirrors every `.py` under host `../Test/` into `dagster/tests/` — those files (`tests/Test/**/test_*.py`, `tests/DailyMission/**`, …) use Airtest star-imports and crash collection. Retarget the mirror to a gitignored `tests_mirror/` directory, add a pytest config, and remove the synced copies from git.

**Files:**
- Modify: `report_server.py:590` (sync target)
- Create: `pytest.ini`
- Modify: `.gitignore`
- Delete (git rm): `tests/DailyMission/`, `tests/HeartSystem/`, `tests/LavaQuest/`, `tests/MagicBean/`, `tests/RoyalPass/`, `tests/Test/`, `tests/player-profile/`

**Interfaces:**
- Produces: `pytest.ini` with `testpaths = tests`; `tests/` contains ONLY the three unit test files + `__init__.py`. Mirror lives at `tests_mirror/` (gitignored). Later tasks assume `python -m pytest tests -q` collects exactly the unit tests.

- [ ] **Step 1: Reproduce the collection failure**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests -q`
Expected: 0 collected / collection errors mentioning files under `tests\Test\` or `tests\DailyMission\` (Airtest imports).

- [ ] **Step 2: Retarget the sync thread**

In `report_server.py`, `sync_tests()` currently has:

```python
        source = str(TEST_ROOT)
        target = str(_project_root / "dagster" / "tests")
```

Change the target line to:

```python
        target = str(_dagster_dir / "tests_mirror")
```

- [ ] **Step 3: Create `pytest.ini`**

Create `pytest.ini` at repo root:

```ini
[pytest]
testpaths = tests
norecursedirs = *.air tests_mirror pixon
```

- [ ] **Step 4: Gitignore the mirror and remove synced copies from git**

Append to `.gitignore`:

```
tests_mirror/
```

Then remove the synced suite copies (they are auto-generated mirrors of host `../Test/`, committed by accident):

```powershell
git rm -r --cached tests/DailyMission tests/HeartSystem tests/LavaQuest tests/MagicBean tests/RoyalPass tests/Test tests/player-profile
Remove-Item -Recurse -Force tests/DailyMission, tests/HeartSystem, tests/LavaQuest, tests/MagicBean, tests/RoyalPass, tests/Test, tests/player-profile
```

- [ ] **Step 5: Verify collection works**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests -q`
Expected: `9 passed` (3 report_data + 4 report_server + 2 ldplayer_ctl), 0 errors. (If Task 1 not yet merged, 8 passed 1 failed is acceptable here — the count that matters is 9 collected.)

- [ ] **Step 6: Commit**

```powershell
git add report_server.py pytest.ini .gitignore
git commit -m "fix: retarget test sync to gitignored tests_mirror/, restore pytest collection"
```

---

### Task 3: Refuse port double-bind (Windows SO_REUSEADDR quirk)

Two `report_server.py` instances can bind 127.0.0.1:7070 simultaneously on Windows because `ThreadingHTTPServer` sets `allow_reuse_address = 1`; traffic then lands on an unpredictable (possibly wedged) instance and the browser gets empty replies. This happened on 2026-07-07. Make the second launch fail fast.

**Files:**
- Modify: `report_server.py:576` (server class)
- Test: `tests/test_report_server.py`

**Interfaces:**
- Produces: class `ReportServer(ThreadingHTTPServer)` with `allow_reuse_address = False`, used by `main()`. Tests import it as `rs.ReportServer`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report_server.py` (it already does `import dagster.report_server as rs`):

```python
def test_second_bind_same_port_fails():
    """Two servers must not silently share one port (Windows SO_REUSEADDR quirk)."""
    s1 = rs.ReportServer(("127.0.0.1", 0), rs.ReportHandler)
    port = s1.server_address[1]
    try:
        with pytest.raises(OSError):
            s2 = rs.ReportServer(("127.0.0.1", port), rs.ReportHandler)
            s2.server_close()
    finally:
        s1.server_close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_server.py::test_second_bind_same_port_fails -v`
Expected: FAIL with `AttributeError: module 'dagster.report_server' has no attribute 'ReportServer'`.

- [ ] **Step 3: Add the server class and use it in `main()`**

In `report_server.py`, directly above `def main():` add:

```python
class ReportServer(ThreadingHTTPServer):
    # Two instances silently double-bind one port on Windows with SO_REUSEADDR;
    # fail fast with "address already in use" instead.
    allow_reuse_address = False
```

And in `main()` change:

```python
    server = ThreadingHTTPServer((args.host, args.port), ReportHandler)
```

to:

```python
    server = ReportServer((args.host, args.port), ReportHandler)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_server.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add report_server.py tests/test_report_server.py
git commit -m "fix: refuse port double-bind with exclusive ReportServer bind"
```

---

### Task 4: Fix `/delete/` log-list operator-precedence bug

`report_server.py:204`: `if item.is_file() and item.suffix in ('.txt', '.log') or item.name.startswith('log')` parses as `(A and B) or C` — a directory named `log*` passes the filter. The list is only echoed in the response JSON, but fix the logic.

**Files:**
- Modify: `report_server.py:204`
- Test: none (response-cosmetic; covered by manual delete in Task 10 verification)

**Interfaces:**
- Consumes/Produces: unchanged endpoint shape `{"deleted": name, "logs_cleared": [...]}`.

- [ ] **Step 1: Fix the condition**

Change:

```python
                    if item.is_file() and item.suffix in ('.txt', '.log') or item.name.startswith('log'):
```

to:

```python
                    if item.is_file() and (item.suffix in ('.txt', '.log') or item.name.startswith('log')):
```

- [ ] **Step 2: Sanity run**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests -q`
Expected: all pass (no regression).

- [ ] **Step 3: Commit**

```powershell
git add report_server.py
git commit -m "fix: parenthesize log-file filter in /delete/ handler"
```

---

### Task 5: `/rerun-logs/` — reject bad `offset` with 400 instead of crashing the handler

`report_server.py:529`: `offset = int(query.get("offset", ["0"])[0])` raises `ValueError` on `?offset=abc`, killing the request with no response.

**Files:**
- Modify: `report_server.py:527-529` (`_handle_rerun_logs`)
- Test: `tests/test_report_server.py`

**Interfaces:**
- Produces: module-level helper `parse_offset(query: dict) -> int | None` in `report_server.py` (None = invalid). `_handle_rerun_logs` returns 400 JSON `{"error": "bad offset"}` on None.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report_server.py`:

```python
def test_parse_offset_valid_invalid():
    assert rs.parse_offset({"offset": ["42"]}) == 42
    assert rs.parse_offset({}) == 0
    assert rs.parse_offset({"offset": ["abc"]}) is None
    assert rs.parse_offset({"offset": ["-5"]}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_server.py::test_parse_offset_valid_invalid -v`
Expected: FAIL with `AttributeError: ... no attribute 'parse_offset'`.

- [ ] **Step 3: Implement**

In `report_server.py`, add above `class ReportHandler`:

```python
def parse_offset(query: dict) -> int | None:
    """Parse a non-negative ?offset= value; None if malformed."""
    try:
        offset = int(query.get("offset", ["0"])[0])
    except (ValueError, TypeError):
        return None
    return offset if offset >= 0 else None
```

In `_handle_rerun_logs`, replace:

```python
        from urllib.parse import parse_qs
        query = parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
        offset = int(query.get("offset", ["0"])[0])
```

with:

```python
        from urllib.parse import parse_qs
        query = parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
        offset = parse_offset(query)
        if offset is None:
            self._json(400, {"error": "bad offset"})
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests/test_report_server.py -v`
Expected: all pass (6 tests).

- [ ] **Step 5: Commit**

```powershell
git add report_server.py tests/test_report_server.py
git commit -m "fix: return 400 on malformed rerun-logs offset"
```

---

### Task 6: Refactor — extract duplicated job spawning into `_spawn_job()`

`_handle_run` (`report_server.py:299-342`) and `_handle_rerun` (`report_server.py:360-418`) contain byte-for-byte duplicated Popen/job-dict/prune logic. Extract one helper; both handlers keep their own validation and then delegate.

**Files:**
- Modify: `report_server.py` (`ReportHandler` class)
- Test: existing `tests/test_report_server.py` (behavioral no-op refactor)

**Interfaces:**
- Produces: method `ReportHandler._spawn_job(self, suite: str, stem: str, air_arg: str) -> None` — acquires `_jobs_lock`, sends its own JSON response (409 duplicate / 500 spawn failure / 200 with `{"job_id": ...}`).

- [ ] **Step 1: Add the helper method to `ReportHandler`**

```python
    def _spawn_job(self, suite: str, stem: str, air_arg: str) -> None:
        """Launch dagster_run.py for one .air test and register the job.
        Sends the JSON response itself. Caller must NOT hold _jobs_lock."""
        with _jobs_lock:
            if _find_running_job(suite, stem) is not None:
                self._json(409, {"error": "already running"})
                return
            job_id = str(uuid.uuid4())
            log_path = REPORT_ROOT / f"{job_id}.log"
            log_file = log_path.open("w", encoding="utf-8")
            dagster_run = Path(__file__).parent / "dagster_run.py"
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", str(dagster_run), air_arg],
                    stdout=log_file, stderr=subprocess.STDOUT, env=env,
                )
            except FileNotFoundError:
                log_file.close()
                self._json(500, {"error": "dagster_run.py not found"})
                return
            _jobs[job_id] = {
                "job_id": job_id, "suite": suite, "stem": stem,
                "air_path": air_arg, "proc": proc, "status": "running",
                "new_folder": None, "exit_code": None, "started": time.time(),
                "log_file": log_file, "log_path": log_path,
            }
            _prune_jobs()
        self._json(200, {"job_id": job_id})
```

- [ ] **Step 2: Slim `_handle_run`**

Replace everything in `_handle_run` from `with _jobs_lock:` to the final `self._json(200, {"job_id": job_id})` with:

```python
        self._spawn_job(suite, stem, str(p))
```

- [ ] **Step 3: Slim `_handle_rerun`**

Replace everything in `_handle_rerun` from `with _jobs_lock:` to the final `self._json(200, {"job_id": job_id})` with:

```python
        self._spawn_job(suite, stem, air_path)
```

(Note: `_handle_rerun` passes the relative `air_path` string exactly as before; `_handle_run` passes the resolved absolute path exactly as before.)

- [ ] **Step 4: Run tests + smoke test**

Run: `cd D:\AutoRebase\dagster; python -m pytest tests -q` → all pass.
Start dev server (port 7171 preview config), open Test Catalog tab, click ▶ Run on one test, confirm a `job_id` is returned (job status chip appears) — then ⏹ Terminate it.

- [ ] **Step 5: Commit**

```powershell
git add report_server.py
git commit -m "refactor: extract duplicated job spawning into _spawn_job"
```

---

### Task 7: UI — surface API errors (banner) and fix stuck job status on poll failure

Two frontend defects: (a) when an API endpoint returns 500 the UI silently shows stale data (`online` flag only covers network throw); (b) `pollJob()`'s catch clears the interval but leaves `jobs[key].status === 'running'`, permanently disabling the Run/Rerun button.

**Files:**
- Modify: `static/app.js` (`fetchData`, `pollJob`, state)
- Modify: `static/index.html` (banner markup)
- Modify: `static/styles.css` (banner style)

**Interfaces:**
- Produces: Alpine state `apiError: ''` (empty = healthy). Banner div shows it. `pollJob` sets `{status: 'poll error'}` terminal state.

- [ ] **Step 1: Add `apiError` state and set it in `fetchData`**

In `static/app.js` state block, after `online: true,` add:

```javascript
        apiError: '',
```

Replace `fetchData()` with:

```javascript
        async fetchData() {
            try {
                this.loading = true;
                const headers = this.etag ? { 'If-None-Match': this.etag } : {};
                const res = await fetch('/api/runs', { headers });
                this.online = true;
                if (res.status === 200) {
                    this.runs = await res.json();
                    this.etag = res.headers.get('ETag');
                    await this.fetchMetrics();
                    await this.fetchCatalog();
                    this.apiError = '';
                } else if (res.status !== 304) {
                    const body = await res.json().catch(() => ({}));
                    this.apiError = `API error ${res.status}: ${body.error || 'unexpected response'}`;
                }
            } catch (err) {
                this.online = false;
            } finally {
                this.loading = false;
            }
        },
```

- [ ] **Step 2: Fix `pollJob` stuck status**

In `pollJob()`, replace the catch block:

```javascript
                    } catch(e) {
                        clearInterval(interval);
                        resolve('error');
                    }
```

with:

```javascript
                    } catch(e) {
                        clearInterval(interval);
                        this.jobs[key] = { status: 'poll error' };
                        resolve('error');
                    }
```

- [ ] **Step 3: Add the banner to `index.html`**

Directly under the `<h1>…</h1>` block insert:

```html
    <div class="api-error-banner" x-show="apiError" x-text="apiError"></div>
```

- [ ] **Step 4: Style it in `styles.css`**

Append:

```css
.api-error-banner {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid var(--fail);
  color: var(--fail);
  border-radius: var(--r);
  padding: 10px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  font-family: monospace;
  white-space: pre-wrap;
}
```

- [ ] **Step 5: Verify**

Start dev server. Healthy state: no banner, console clean. Force a 500: in devtools console run `fetch = ((orig) => (url, o) => url === '/api/runs' ? Promise.resolve(new Response('{"error":"boom"}', {status: 500})) : orig(url, o))(fetch)` — within 3s the red banner shows `API error 500: boom`. Reload the page (restores real fetch) — banner clears. Separately stop the server process — "offline" indicator appears (existing network-throw path).

- [ ] **Step 6: Commit**

```powershell
git add static/app.js static/index.html static/styles.css
git commit -m "feat(ui): surface API errors in banner, fix stuck job status on poll failure"
```

---

### Task 8: UI — live log viewer for running jobs (wire up dead `/rerun-logs/` endpoint)

The server already implements `GET /rerun-logs/<job_id>?offset=N` (incremental log tail) but nothing in the UI calls it. Add a collapsible live-log panel per running job in both Report and Catalog tabs.

**Files:**
- Modify: `static/app.js` (state + `toggleLogs`, extend `pollJob`)
- Modify: `static/index.html` (log panel markup, both tabs)
- Modify: `static/styles.css` (panel style)

**Interfaces:**
- Consumes: `GET /rerun-logs/<job_id>?offset=N` → `{"text": str, "offset": int}` (existing).
- Produces: Alpine state `logView: { key: null, text: '', offset: 0 }`; method `toggleLogs(key)`. Log text fetched on the existing 2s poll tick for the open panel only.

- [ ] **Step 1: Add state and toggle method in `app.js`**

State block, after `jobs: {},`:

```javascript
        logView: { key: null, text: '', offset: 0 }, // one open log panel at a time
```

New methods (after `pollJob`):

```javascript
        toggleLogs(key) {
            if (this.logView.key === key) {
                this.logView = { key: null, text: '', offset: 0 };
            } else {
                this.logView = { key: key, text: '', offset: 0 };
                this.fetchLogs();
            }
        },

        async fetchLogs() {
            const key = this.logView.key;
            if (!key) return;
            const jobId = this.jobs[key]?.job_id;
            if (!jobId) return;
            try {
                const res = await fetch(`/rerun-logs/${encodeURIComponent(jobId)}?offset=${this.logView.offset}`);
                if (!res.ok) return;
                const data = await res.json();
                if (this.logView.key !== key) return; // panel switched while fetching
                if (data.text) this.logView.text += data.text;
                this.logView.offset = data.offset;
            } catch (e) { /* next tick retries */ }
        },
```

- [ ] **Step 2: Poll logs on the job tick**

In `pollJob()`, at the top of the `setInterval` callback (before the `/rerun-status/` fetch), add:

```javascript
                    if (this.logView.key === key) this.fetchLogs();
```

- [ ] **Step 3: Add "Logs" button + panel in `index.html` (Report tab)**

In the Report tab run row, next to the Terminate button (after line with `⏹ Terminate`), add:

```html
                    <button class="action-btn" x-show="jobs[r.folder]?.job_id" @click="toggleLogs(r.folder)" x-text="logView.key === r.folder ? 'Hide Logs' : 'Logs'"></button>
```

Directly after the `</div>` closing `run-meta` (still inside the `<li>`), add:

```html
                  <pre class="job-log" x-show="logView.key === r.folder" x-text="logView.text || '(waiting for output…)'"></pre>
```

Note: the `<li>` is `display:flex`; the panel must wrap. Change that `<li>` to `<li style="flex-wrap: wrap;">` or (preferred) add `flex-wrap: wrap;` to the `li` rule in `styles.css`.

- [ ] **Step 4: Same for Catalog tab**

Next to the catalog Terminate button add:

```html
                    <button class="action-btn" x-show="jobs[t]?.job_id" @click="toggleLogs(t)" x-text="logView.key === t ? 'Hide Logs' : 'Logs'"></button>
```

And after that row's `run-meta` div:

```html
                  <pre class="job-log" x-show="logView.key === t" x-text="logView.text || '(waiting for output…)'"></pre>
```

- [ ] **Step 5: Style the panel**

Append to `styles.css` (and add `flex-wrap: wrap;` to the existing `li` rule):

```css
.job-log {
  flex-basis: 100%;
  max-height: 260px;
  overflow-y: auto;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 10px 12px;
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
```

- [ ] **Step 6: Verify end-to-end**

Start dev server, run a catalog test, click "Logs" — panel streams `dagster_run.py` stdout incrementally; close/reopen resets and re-streams from offset 0; terminate the test.

- [ ] **Step 7: Commit**

```powershell
git add static/app.js static/index.html static/styles.css
git commit -m "feat(ui): live log viewer for running jobs via /rerun-logs"
```

---

### Task 9: UI — de-inline benchmark table styles, pause polling when tab hidden, show last-updated

Cleanup pass: the Benchmark tab (`static/index.html:136-170`) carries ~30 repeated inline style attributes — move to classes. Polling every 3s continues when the tab is hidden — skip ticks. Users can't tell data freshness — show a last-updated stamp.

**Files:**
- Modify: `static/index.html:136-170` (benchmark table), header line
- Modify: `static/app.js` (`init`, `fetchData`, state)
- Modify: `static/styles.css`

**Interfaces:**
- Produces: CSS classes `.bench-table`, `.bench-table th`, `.bench-table td`, `.td-num`, `.td-score`; Alpine state `lastUpdated: null`.

- [ ] **Step 1: Add classes to `styles.css`**

```css
.bench-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
  background: var(--bg-card); border: 1px solid var(--border);
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.bench-table thead { position: sticky; top: 0; background: var(--bg-item); z-index: 10; }
.bench-table th {
  padding: 8px 12px; font-weight: 600; text-align: left;
  border: 1px solid var(--border); border-bottom: 2px solid var(--border); white-space: nowrap;
}
.bench-table td { padding: 8px 12px; border: 1px solid var(--border); white-space: nowrap; }
.bench-table tbody tr:nth-child(even) { background: var(--bg-item); }
.bench-table tbody tr:hover { filter: brightness(1.5); }
.td-num { font-family: monospace; text-align: right; color: var(--text-dim); }
.td-score { font-family: monospace; text-align: center; font-weight: bold; }
```

- [ ] **Step 2: Rewrite the benchmark table markup**

Replace `static/index.html` lines 138-165 (the `<table …>` … `</table>`) with:

```html
        <table class="bench-table">
          <thead>
            <tr>
              <th>Test Case</th><th>Runs</th><th>Avg (s)</th><th>Median (s)</th>
              <th>Min (s)</th><th>Max (s)</th><th style="text-align:center;">Score (Max 100)</th>
            </tr>
          </thead>
          <tbody>
            <template x-for="b in benchmarks" :key="b.stem">
              <tr>
                <td style="font-weight:500;" x-text="b.stem"></td>
                <td class="td-num" x-text="b.runs"></td>
                <td class="td-num" style="color:var(--text-main);" x-text="b.avg"></td>
                <td class="td-num" x-text="b.median"></td>
                <td class="td-num" x-text="b.min"></td>
                <td class="td-num" x-text="b.max"></td>
                <td class="td-score" :style="`color: ${b.score >= 80 ? 'var(--pass)' : (b.score >= 50 ? 'var(--warn)' : 'var(--fail)')};`" x-text="b.score"></td>
              </tr>
            </template>
          </tbody>
        </table>
```

(The zebra striping moves from the `:style` binding to CSS `nth-child`; the `i` loop index is no longer needed.)

- [ ] **Step 3: Pause polling when hidden + last-updated**

In `app.js` state add `lastUpdated: null,`. In `init()` change the interval line to:

```javascript
            setInterval(() => { if (!document.hidden) this.fetchData(); }, 3000);
```

At the end of the `res.status === 200` branch in `fetchData()` (after `this.apiError = '';`) add:

```javascript
                    this.lastUpdated = new Date();
```

In `index.html` `<h1>`, after the "offline" span, add:

```html
      <span x-show="lastUpdated" style="font-size: 12px; font-weight: normal; color: var(--text-dim); margin-left: auto;" x-text="lastUpdated ? 'updated ' + lastUpdated.toLocaleTimeString() : ''"></span>
```

- [ ] **Step 4: Verify**

Dev server: Benchmark tab renders identically (zebra rows, hover brighten, score colors); switch OS window away >6s, return — "updated" stamp lags then refreshes; no console errors.

- [ ] **Step 5: Commit**

```powershell
git add static/index.html static/app.js static/styles.css
git commit -m "refactor(ui): de-inline benchmark styles; pause hidden-tab polling; last-updated stamp"
```

---

### Task 10: Lint gate — ruff config scoped to runner code + autofixes

`ruff check .` reports 737 errors, almost all F405 star-import noise from mirrored Airtest suites (gone after Task 2) and vendored `pixon/`. Scope ruff to the runner's own code, apply safe autofixes, and record the clean command.

**Files:**
- Create: `ruff.toml`
- Modify: whatever files `ruff --fix` touches (safe fixes only; review diff)

**Interfaces:**
- Produces: `ruff check .` exits 0 from repo root (the gate future tasks can rely on).

- [ ] **Step 1: Create `ruff.toml`**

```toml
# Lint only the runner's own code — mirrored .air suites and vendored pixon
# follow Airtest star-import conventions and are not ours to restyle.
exclude = [
    "tests_mirror",
    "pixon",
    "graphify-out",
    "scrcpy-win64",
    "static",
]

[lint]
select = ["E4", "E7", "E9", "F"]
```

- [ ] **Step 2: Baseline count on scoped code**

Run: `cd D:\AutoRebase\dagster; python -m ruff check . --statistics`
Expected: a small number of findings (the 700+ F405s from mirrored suites are excluded). Note the count.

- [ ] **Step 3: Apply safe autofixes and review**

```powershell
python -m ruff check . --fix
git diff --stat
```

Review the diff — safe fixes only (unused imports, etc.). Fix any remaining findings by hand: each remaining line is listed by `python -m ruff check .` with file:line and rule; resolve them one by one (unused variables → delete; undefined names → import or correct).

- [ ] **Step 4: Verify gate + tests**

Run: `cd D:\AutoRebase\dagster; python -m ruff check .` → exits 0, "All checks passed".
Run: `cd D:\AutoRebase\dagster; python -m pytest tests -q` → all pass.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "chore: scope ruff to runner code, fix lint findings"
```

---

## Verification (whole plan)

1. `cd D:\AutoRebase\dagster; python -m pytest tests -q` → **all collected, all pass** (was: 0 collected / 1 failing).
2. `python -m ruff check .` → exits 0.
3. Start `report_server.py` twice on port 7070 → second exits with "address already in use" (was: silent double-bind, blank browser).
4. Dashboard manual pass: trend chart with 1 day of data, API-error banner, live Logs panel on a running job, benchmark tab visuals unchanged, "updated HH:MM:SS" stamp ticking.
5. `git status` → no auto-synced `.air` copies reappear under `tests/` (mirror now in gitignored `tests_mirror/`).

## Out of scope (deliberate)

- `reports/aggregate_report.py` (922 lines, legacy static `report.html` builder) duplicates the live dashboard's grouping/benchmark logic. Deleting or splitting it changes user-visible artifacts (`report.html` regenerated after every run) — needs a product decision, not a refactor task. Revisit separately.
- Vendored `pixon/` copy inside this repo (4.6 MB, committed 2026-07-07) — possibly accidental; removal is a one-liner but needs owner confirmation.
- The 3s full-refetch polling could become smarter (ETag already trims payloads); WebSockets/SSE would be over-engineering for a local tool.
