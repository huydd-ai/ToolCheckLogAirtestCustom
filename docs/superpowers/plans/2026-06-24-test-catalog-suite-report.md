# Test Catalog + Suite-Grouped Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Test Catalog tab that browses every `.air` in `../Test/` (run or not) with live-monitored Run buttons, and regroup the global report by suite folder → day → runs.

**Architecture:** Pure extension of `aggregate_report.py` (data + server-rendered HTML) and `report_server.py` (a new `/run` endpoint). A `suite` field on `RunEntry`, derived from the `AIR_PATH=` line each run's `log.txt` already carries, powers both the new grouping and the catalog↔history join. `/run` reuses the existing `_jobs` / `/rerun-logs` / `/rerun-status` / `/rerun-terminate` machinery for live logs and lifecycle.

**Tech Stack:** Python 3 stdlib (`http.server`, `pathlib`, `re`, `dataclasses`), pytest. No new dependencies. Browser side is vanilla JS already inline in `aggregate_report.py`.

---

## Background facts (read once)

- Run folders: `report_run/<stem>_<YYYYMMDD>_<HHMMSS>/`. Folder name carries **stem + timestamp only** — NOT the suite.
- Suite lives only in `log.txt` line 1: `AIR_PATH=<resolved absolute path>` (e.g. `D:\AutoRebase\Test\HeartSystem\tc01_x.air`). Written on every run by `reporting.write_log_txt` (called at `runner.py:164`). Suite = `Path(air_path).parent.name`.
- `aggregate_report.py` is at `dagster/aggregate_report.py`; `../Test` resolves to `Path(__file__).resolve().parent.parent / "Test"`.
- `render_html(groups)` today takes `list[(date_str, list[RunEntry])]` from `group_by_date`. After this plan it takes suite-grouped data — **every existing `render_html(group_by_date(...))` call in tests must change** (Task 5). Both `test_aggregate_report.py` and `test_rerun.py` contain such calls.
- `report_server.py` already binds `0.0.0.0`. `/run` accepts a client path → it MUST be confined to `../Test/` (Task 9).

Run all tests with: `python -m pytest test_aggregate_report.py test_rerun.py -q` from `dagster/`.

---

### Task 1: `suite` field on `RunEntry`, populated in `scan_runs`

**Files:**
- Modify: `aggregate_report.py` (RunEntry dataclass ~52-59, scan_runs ~61-87, add helper near `extract_device`)
- Test: `test_aggregate_report.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_aggregate_report.py`:

```python
def test_extract_suite_from_air_path(tmp_path):
    from aggregate_report import extract_suite
    log = tmp_path / "log.txt"
    log.write_text("AIR_PATH=/x/Test/HeartSystem/tc01.air\n# Status: PASS\n", encoding="utf-8")
    assert extract_suite(log) == "HeartSystem"


def test_extract_suite_missing_air_path(tmp_path):
    from aggregate_report import extract_suite
    log = tmp_path / "log.txt"
    log.write_text("# Status: PASS\n", encoding="utf-8")
    assert extract_suite(log) == "unknown"


def test_scan_runs_populates_suite(tmp_path):
    d = tmp_path / "tc01_foo_20260612_102041"
    d.mkdir()
    (d / "log.txt").write_text(
        "AIR_PATH=/x/Test/HeartSystem/tc01_foo.air\n# Status: PASS\n", encoding="utf-8"
    )
    entries = scan_runs(tmp_path)
    assert entries[0].suite == "HeartSystem"


def test_scan_runs_suite_unknown_when_no_air_path(tmp_path):
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")  # helper writes no AIR_PATH
    entries = scan_runs(tmp_path)
    assert entries[0].suite == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_aggregate_report.py -k "suite" -q`
Expected: FAIL — `ImportError: cannot import name 'extract_suite'` / `RunEntry` has no `suite`.

- [ ] **Step 3: Implement**

In `aggregate_report.py`, add a regex near the others (after `_DEVICE_RE`, ~line 18):

```python
_AIR_PATH_RE = re.compile(r"^AIR_PATH=(.+)$", re.MULTILINE)
```

Add a helper after `extract_device` (~line 50):

```python
def extract_suite(log_path: Path) -> str:
    """Suite = parent dir name of AIR_PATH in log.txt head. 'unknown' if absent."""
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            head = f.read(1024)
    except OSError:
        return "unknown"
    m = _AIR_PATH_RE.search(head)
    if not m:
        return "unknown"
    return Path(m.group(1).strip()).parent.name or "unknown"
```

Add `suite` to the dataclass (after `device`):

```python
@dataclass(frozen=True)
class RunEntry:
    stem: str
    when: datetime
    status: str
    folder: str
    report_href: str
    device: str = "unknown"
    suite: str = "unknown"
```

In `scan_runs`, after `device = extract_device(log_path)`:

```python
        suite = extract_suite(log_path)
```

and add `suite=suite,` to the `RunEntry(...)` construction.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_aggregate_report.py -k "suite" -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: add suite field to RunEntry derived from AIR_PATH"
```

---

### Task 2: `group_by_suite_then_date`

**Files:**
- Modify: `aggregate_report.py` (add after `group_by_date`, ~line 96)
- Test: `test_aggregate_report.py`

- [ ] **Step 1: Write the failing tests**

Add a suite-aware entry helper and tests to `test_aggregate_report.py`:

```python
def _entry_s(stem, dt_str, status, suite):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    folder = f"{stem}_{dt.strftime('%Y%m%d_%H%M%S')}"
    return RunEntry(stem, dt, status, folder, f"{folder}/report.html", suite=suite)


def test_group_by_suite_then_date_nests():
    from aggregate_report import group_by_suite_then_date
    entries = [
        _entry_s("a", "2026-06-12 10:00:00", "PASS", "HeartSystem"),
        _entry_s("b", "2026-06-11 10:00:00", "PASS", "HeartSystem"),
        _entry_s("c", "2026-06-12 10:00:00", "PASS", "DailyMission"),
    ]
    groups = group_by_suite_then_date(entries)
    suites = [s for s, _ in groups]
    assert suites == ["DailyMission", "HeartSystem"]  # alpha
    heart = dict(groups)["HeartSystem"]
    assert [d for d, _ in heart] == ["2026-06-12", "2026-06-11"]  # date desc


def test_group_by_suite_then_date_unknown_sorts_last():
    from aggregate_report import group_by_suite_then_date
    entries = [
        _entry_s("a", "2026-06-12 10:00:00", "PASS", "unknown"),
        _entry_s("b", "2026-06-12 10:00:00", "PASS", "HeartSystem"),
    ]
    assert [s for s, _ in group_by_suite_then_date(entries)] == ["HeartSystem", "unknown"]


def test_group_by_suite_then_date_empty():
    from aggregate_report import group_by_suite_then_date
    assert group_by_suite_then_date([]) == []
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_aggregate_report.py -k "group_by_suite" -q`
Expected: FAIL — `cannot import name 'group_by_suite_then_date'`.

- [ ] **Step 3: Implement**

Add after `group_by_date` in `aggregate_report.py`:

```python
def group_by_suite_then_date(
    entries: list[RunEntry],
) -> list[tuple[str, list[tuple[str, list[RunEntry]]]]]:
    by_suite: dict[str, list[RunEntry]] = {}
    for e in entries:
        by_suite.setdefault(e.suite, []).append(e)
    # "unknown" sorts last, others alphabetical
    suite_keys = sorted(by_suite, key=lambda s: (s == "unknown", s))
    return [(s, group_by_date(by_suite[s])) for s in suite_keys]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py -k "group_by_suite" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: add group_by_suite_then_date grouping"
```

---

### Task 3: `scan_catalog` — filesystem scan of `../Test/`

**Files:**
- Modify: `aggregate_report.py` (add after `scan_runs`)
- Test: `test_aggregate_report.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_scan_catalog_lists_air_by_suite(tmp_path):
    from aggregate_report import scan_catalog
    (tmp_path / "HeartSystem").mkdir()
    (tmp_path / "HeartSystem" / "tc01_a.air").write_text("", encoding="utf-8")
    (tmp_path / "HeartSystem" / "tc02_b.air").write_text("", encoding="utf-8")
    (tmp_path / "DailyMission").mkdir()
    (tmp_path / "DailyMission" / "tc01_x.air").write_text("", encoding="utf-8")
    cat = scan_catalog(tmp_path)
    assert cat == {
        "DailyMission": ["tc01_x"],
        "HeartSystem": ["tc01_a", "tc02_b"],
    }


def test_scan_catalog_excludes_pycache(tmp_path):
    from aggregate_report import scan_catalog
    suite = tmp_path / "HeartSystem"
    suite.mkdir()
    (suite / "tc01_a.air").write_text("", encoding="utf-8")
    pyc = suite / "__pycache__"
    pyc.mkdir()
    (pyc / "junk.air").write_text("", encoding="utf-8")  # must NOT appear
    cat = scan_catalog(tmp_path)
    assert cat == {"HeartSystem": ["tc01_a"]}


def test_scan_catalog_missing_root(tmp_path):
    from aggregate_report import scan_catalog
    assert scan_catalog(tmp_path / "nope") == {}
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_aggregate_report.py -k "scan_catalog" -q`
Expected: FAIL — `cannot import name 'scan_catalog'`.

- [ ] **Step 3: Implement**

Add after `scan_runs` in `aggregate_report.py`:

```python
def scan_catalog(test_root: Path) -> dict[str, list[str]]:
    """Map suite folder -> sorted .air stems under test_root/<suite>/. All test cases,
    run or not. .air entries are DIRECTORIES in this repo; the glob matches them one
    level under each suite, and __pycache__ is excluded by the .air suffix."""
    if not test_root.exists():
        return {}
    catalog: dict[str, list[str]] = {}
    for air in test_root.glob("*/*.air"):
        catalog.setdefault(air.parent.name, []).append(air.stem)
    for stems in catalog.values():
        stems.sort()
    return dict(sorted(catalog.items()))
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py -k "scan_catalog" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: add scan_catalog filesystem scan of Test/"
```

---

### Task 4: `build_catalog` — join catalog with run history

**Files:**
- Modify: `aggregate_report.py` (add after `scan_catalog`)
- Test: `test_aggregate_report.py`

Output shape (per suite, per test): `dict` with keys `stem`, `air_path` (e.g. `"Test/HeartSystem/tc01_a.air"`, forward slashes), `last_status` (`str | None`), `last_href` (`str | None`).

- [ ] **Step 1: Write the failing tests**

```python
def test_build_catalog_joins_last_run(tmp_path):
    from aggregate_report import build_catalog
    (tmp_path / "HeartSystem").mkdir()
    (tmp_path / "HeartSystem" / "tc01_a.air").write_text("", encoding="utf-8")
    (tmp_path / "HeartSystem" / "tc02_b.air").write_text("", encoding="utf-8")
    entries = [
        _entry_s("tc01_a", "2026-06-12 09:00:00", "FAIL", "HeartSystem"),
        _entry_s("tc01_a", "2026-06-12 11:00:00", "PASS", "HeartSystem"),  # newer wins
    ]
    cat = build_catalog(tmp_path, entries)
    suite, tests = cat[0]
    assert suite == "HeartSystem"
    by_stem = {t["stem"]: t for t in tests}
    assert by_stem["tc01_a"]["last_status"] == "PASS"
    assert by_stem["tc01_a"]["last_href"] == "tc01_a_20260612_110000/report.html"
    assert by_stem["tc01_a"]["air_path"] == "Test/HeartSystem/tc01_a.air"
    assert by_stem["tc02_b"]["last_status"] is None   # never run
    assert by_stem["tc02_b"]["last_href"] is None


def test_build_catalog_matches_on_suite_and_stem(tmp_path):
    # Same stem in two suites must not cross-contaminate.
    from aggregate_report import build_catalog
    for s in ("HeartSystem", "DailyMission"):
        (tmp_path / s).mkdir()
        (tmp_path / s / "tc01_x.air").write_text("", encoding="utf-8")
    entries = [_entry_s("tc01_x", "2026-06-12 10:00:00", "PASS", "HeartSystem")]
    cat = dict(build_catalog(tmp_path, entries))
    daily = {t["stem"]: t for t in cat["DailyMission"]}
    heart = {t["stem"]: t for t in cat["HeartSystem"]}
    assert heart["tc01_x"]["last_status"] == "PASS"
    assert daily["tc01_x"]["last_status"] is None  # not the HeartSystem run
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_aggregate_report.py -k "build_catalog" -q`
Expected: FAIL — `cannot import name 'build_catalog'`.

- [ ] **Step 3: Implement**

Add after `scan_catalog`:

```python
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
                "air_path": f"Test/{suite}/{stem}.air",
                "last_status": run.status if run else None,
                "last_href": run.report_href if run else None,
            })
        out.append((suite, tests))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py -k "build_catalog" -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: add build_catalog joining catalog with run history"
```

---

### Task 5: Refactor `render_html` to suite → day grouping

This changes `render_html`'s input from date-groups to suite-groups and wraps the existing per-date rendering under a suite `<details>`. **The per-date markup stays byte-for-byte identical** (extracted into a helper), so only the call sites and a few new assertions change.

**Files:**
- Modify: `aggregate_report.py` (`render_html` ~580-685; add `_append_date_group` helper)
- Modify: `test_aggregate_report.py` (every `render_html(group_by_date(...))` call)
- Modify: `test_rerun.py` (lines 318-333: `render_html(group_by_date(...))` calls)

- [ ] **Step 1: Update existing tests to the new signature + add suite assertions**

In `test_aggregate_report.py`, replace each `render_html(group_by_date(X))` with `render_html(group_by_suite_then_date(X))`. Add `group_by_suite_then_date` to the imports at top. The affected test functions: `test_render_html_group_header_has_counts`, `test_render_html_today_open_past_collapsed`, `test_render_html_row_links_to_report`, `test_render_html_status_badge_classes`, `test_render_html_escapes_stem`, `test_render_html_summary_bar_metrics`, `test_render_html_filter_controls`, `test_render_html_run_item_filter_attrs`, `test_render_html_group_has_delete_all_button`, `test_render_html_row_has_delete_button`, `test_render_html_delete_button_uses_folder_name`.

Add one new test:

```python
def test_render_html_groups_by_suite():
    entries = [
        _entry_s("tc01_a", "2026-06-12 10:00:00", "PASS", "HeartSystem"),
        _entry_s("tc01_x", "2026-06-12 10:00:00", "FAIL", "DailyMission"),
    ]
    html = render_html(group_by_suite_then_date(entries))
    assert ">HeartSystem<" in html
    assert ">DailyMission<" in html
```

In `test_rerun.py`, change the import line 304 to add `group_by_suite_then_date` and replace the three `render_html(group_by_date([_make_entry()]))` calls (lines 319, 325, 330) with `render_html(group_by_suite_then_date([_make_entry()]))`.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest test_aggregate_report.py test_rerun.py -k "render or dashboard or suite" -q`
Expected: FAIL — `render_html()` still iterates date-groups, so `group_by_suite_then_date` output (nested) renders wrong / raises `ValueError: too many values to unpack`.

- [ ] **Step 3: Extract the per-date block into a helper**

In `aggregate_report.py`, add this helper just above `render_html`. Its body is the **exact** existing loop body from `render_html` (lines ~637-674), moved verbatim:

```python
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
        time_str = r.when.strftime("%H:%M:%S")
        dev_id = escape(r.device, quote=True)
        html.append(f'<li class="run-item" data-status="{status_cls}" data-name="{escape(r.stem.lower(), quote=True)}" data-device="{dev_id}">')
        html.append('<div class="run-main">')
        html.append(f'<span class="badge {status_cls}">{escape(r.status)}</span>')
        html.append(f'<a class="run-name" href="{href}" onclick="openReport(event, \'{href}\', \'{stem}\')">{stem}</a>')
        html.append('</div>')
        html.append('<div class="run-meta">')
        html.append(f'<span class="dev-tag" title="Device">&#128241; {escape(r.device)}</span>')
        html.append(f'<span class="run-time">{time_str}</span>')
        html.append(f'<button class="rerun-btn" data-folder="{folder}" onclick="rerunTest(this, \'{folder}\')" title="Rerun this test">↺ Rerun</button>')
        html.append(f'<button class="terminate-btn" data-folder="{folder}" onclick="terminateTest(this, \'{folder}\')" title="Terminate this test">⏹ Terminate</button>')
        html.append(f'<button class="logs-btn" data-folder="{folder}" onclick="toggleLogs(\'{folder}\')" title="Toggle CLI Logs">📄 Logs</button>')
        html.append(f'<span class="rerun-status" data-folder="{folder}"></span>')
        html.append(f'<button class="delete-btn" title="Delete Report" onclick="deleteRun(event, \'{folder}\')">')
        html.append('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>')
        html.append('</button>')
        html.append('</div>')
        html.append('</li>')
        html.append(f'<li class="run-logs-container" id="logs-{folder}"><pre id="pre-{folder}"></pre></li>')
    html.append('</ul></div></details>')
```

- [ ] **Step 4: Rewrite `render_html`'s grouping loop**

Change `render_html`'s signature/body. Replace the section from `all_rows = [r for _, rows in groups for r in rows]` computation and the `for date_str, rows in groups:` loop. New version — note `all_rows` now flattens the deeper nesting, and the loop wraps dates under a suite `<details>`:

```python
def render_html(suite_groups: list[tuple[str, list[tuple[str, list[RunEntry]]]]]) -> str:
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

    html.append('</div>')  # end container

    html.append('<div id="modal"><div id="modal-bg"></div><div id="modal-panel">')
    html.append('<div id="modal-bar"><div id="modal-title"></div><button id="modal-close">x</button></div>')
    html.append('<iframe id="modal-frame"></iframe></div></div>')

    html.append(f'<script>{_JS}</script>')
    html.append('</body></html>')
    return "\n".join(html)
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py test_rerun.py -k "render or dashboard or suite" -q`
Expected: PASS. (`test_render_html_today_open_past_collapsed` still passes: suite `<details open>` and a collapsed past-day `<details>` both present.)

- [ ] **Step 6: Run the full suite to catch stragglers**

Run: `python -m pytest test_aggregate_report.py test_rerun.py -q`
Expected: PASS. If any test still calls `group_by_date` into `render_html`, fix it the same way.

- [ ] **Step 7: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py test_rerun.py
git commit -m "feat: regroup report by suite -> day; refactor render_html"
```

---

### Task 6: Render the Test Catalog tab (HTML + CSS + JS)

Adds a `Report | Test Catalog` tab bar, a server-rendered catalog pane, and the `runCatalogTest` / `showTab` JS reusing the existing `pollRerunStatus` live-log poller.

**Files:**
- Modify: `aggregate_report.py` (`render_html` to take catalog + emit tabs; `_CSS`; `_JS`; `_append_catalog` helper)
- Test: `test_aggregate_report.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_render_html_has_tab_bar():
    html = render_html([], catalog=[])
    assert 'data-tab="report"' in html
    assert 'data-tab="catalog"' in html
    assert "function showTab(" in html


def test_render_html_catalog_lists_tests_with_run_button():
    catalog = [("HeartSystem", [
        {"stem": "tc01_a", "air_path": "Test/HeartSystem/tc01_a.air", "last_status": "PASS",
         "last_href": "tc01_a_20260612_110000/report.html"},
        {"stem": "tc02_b", "air_path": "Test/HeartSystem/tc02_b.air", "last_status": None, "last_href": None},
    ])]
    html = render_html([], catalog=catalog)
    assert ">HeartSystem<" in html
    assert "tc01_a" in html
    assert "runCatalogTest(this, 'cat0', 'Test/HeartSystem/tc01_a.air')" in html
    assert "never run" in html        # tc02_b badge
    assert "function runCatalogTest(" in html


def test_render_html_catalog_escapes_paths():
    catalog = [("S", [{"stem": "t<x>", "air_path": "Test/S/t<x>.air", "last_status": None, "last_href": None}])]
    html = render_html([], catalog=catalog)
    assert "t<x>" not in html
    assert "&lt;x&gt;" in html
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_aggregate_report.py -k "catalog or tab_bar" -q`
Expected: FAIL — `render_html()` takes no `catalog` kwarg.

- [ ] **Step 3: Add the `catalog` param + tab scaffolding to `render_html`**

Change the signature and wrap the existing report body in a tab pane, then add the catalog pane. Replace the signature line and the two structural points:

Signature:
```python
def render_html(
    suite_groups: list[tuple[str, list[tuple[str, list[RunEntry]]]]],
    catalog: list[tuple[str, list[dict]]] | None = None,
) -> str:
```

Right after `'<h1>Dagster Test Reports</h1>'` and the banner line, insert the tab bar + open the report pane:
```python
        '<div class="tabs">',
        '<button class="tab-btn active" data-tab="report" onclick="showTab(\'report\')">Report</button>',
        '<button class="tab-btn" data-tab="catalog" onclick="showTab(\'catalog\')">Test Catalog</button>',
        '</div>',
        '<div id="tab-report" class="tab-pane active">',
```

Immediately before `html.append('</div>')  # end container`, close the report pane and emit the catalog pane:
```python
    html.append('</div>')  # end tab-report
    html.append('<div id="tab-catalog" class="tab-pane">')
    _append_catalog(html, catalog or [])
    html.append('</div>')  # end tab-catalog
```

- [ ] **Step 4: Add the `_append_catalog` helper**

Add above `render_html`:

```python
def _append_catalog(html: list[str], catalog: list[tuple[str, list[dict]]]) -> None:
    if not catalog:
        html.append('<p class="empty-state">No test root found (../Test missing).</p>')
        return
    idx = 0
    for suite, tests in catalog:
        html.append('<details open class="suite-group">')
        html.append(f'<summary class="suite-summary"><span>{escape(suite)} &mdash; {len(tests)} tests</span></summary>')
        html.append('<div class="group-content"><ul>')
        for t in tests:
            key = f"cat{idx}"
            idx += 1
            stem = escape(t["stem"])
            air = escape(t["air_path"], quote=True)
            status = t["last_status"]
            status_cls = status.lower() if status in {"PASS", "FAIL", "SKIP"} else "unknown"
            badge = escape(status) if status else "never run"
            html.append('<li class="run-item">')
            html.append('<div class="run-main">')
            html.append(f'<span class="badge {status_cls}">{badge}</span>')
            if t["last_href"]:
                href = escape(t["last_href"], quote=True)
                html.append(f'<a class="run-name" href="{href}" onclick="openReport(event, \'{href}\', \'{stem}\')">{stem}</a>')
            else:
                html.append(f'<span class="run-name">{stem}</span>')
            html.append('</div>')
            html.append('<div class="run-meta">')
            html.append(f'<button class="rerun-btn" onclick="runCatalogTest(this, \'{key}\', \'{air}\')" title="Run this test">▶ Run</button>')
            html.append(f'<button class="terminate-btn" id="cat-term-{key}" data-folder="{key}" onclick="terminateTest(this, \'{key}\')" style="display:none">⏹ Terminate</button>')
            html.append(f'<button class="logs-btn" onclick="toggleLogs(\'{key}\')" title="Toggle CLI Logs">📄 Logs</button>')
            html.append(f'<span class="rerun-status" id="cat-status-{key}"></span>')
            html.append('</div>')
            html.append('</li>')
            html.append(f'<li class="run-logs-container" id="logs-{key}"><pre id="pre-{key}"></pre></li>')
        html.append('</ul></div></details>')
```

- [ ] **Step 5: Add CSS** — append to the `_CSS` string (before its closing `""".strip()`):

```css
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab-btn { background: var(--bg); border: 1px solid var(--border); color: var(--text-dim); padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.tab-btn.active { color: var(--text-main); border-color: var(--accent); }
.tab-pane { display: none; }
.tab-pane.active { display: block; }
.suite-summary { font-weight: 700; }
.suite-content { padding-left: 8px; }
```

- [ ] **Step 6: Add JS** — append to the `_JS` string (before its closing `"""`):

```javascript
function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  var pane = document.getElementById('tab-' + name);
  if (pane) pane.classList.add('active');
  var btn = document.querySelector('.tab-btn[data-tab="' + name + '"]');
  if (btn) btn.classList.add('active');
}

async function runCatalogTest(btn, key, airPath) {
  btn.disabled = true;
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
    _rerunActive = true;
    pollRerunStatus(btn, key, data.job_id, statusEl, termBtn, null, preEl, logsContainer);
  } catch (err) {
    btn.disabled = false; btn.textContent = orig;
    if (statusEl) statusEl.textContent = 'Server offline';
  }
}
```

Note: on completion `pollRerunStatus` relabels `btn.textContent` to `'↺ Rerun'` and triggers `refreshRunList()` → full page reload (resetting to the Report tab and restoring correct labels from server HTML). Acceptable for v1 — the finished run's report is then visible.

- [ ] **Step 7: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py -k "catalog or tab_bar" -q`
Expected: PASS (4 tests).

- [ ] **Step 8: Run full report suite**

Run: `python -m pytest test_aggregate_report.py test_rerun.py -q`
Expected: PASS (all).

- [ ] **Step 9: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: add Test Catalog tab with live-monitored Run buttons"
```

---

### Task 7: Wire catalog into `regenerate_global_report`

**Files:**
- Modify: `aggregate_report.py` (`regenerate_global_report` ~687-694)
- Test: `test_aggregate_report.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_regenerate_renders_suite_groups_and_catalog(tmp_path):
    # report_run with one run
    run = tmp_path / "report_run"
    run.mkdir()
    d = run / "tc01_a_20260612_110000"
    d.mkdir()
    (d / "log.txt").write_text(
        "AIR_PATH=/x/Test/HeartSystem/tc01_a.air\n# Status: PASS\n", encoding="utf-8"
    )
    # Test/ root with a never-run case
    test_root = tmp_path / "Test"
    (test_root / "HeartSystem").mkdir(parents=True)
    (test_root / "HeartSystem" / "tc01_a.air").write_text("", encoding="utf-8")
    (test_root / "HeartSystem" / "tc99_never.air").write_text("", encoding="utf-8")
    out = regenerate_global_report(run, test_root=test_root)
    txt = out.read_text(encoding="utf-8")
    assert ">HeartSystem<" in txt        # suite group in report tab
    assert "tc99_never" in txt           # never-run case in catalog
    assert 'data-tab="catalog"' in txt


def test_regenerate_default_test_root_no_crash(tmp_path):
    # No test_root passed -> defaults to ../Test relative to module; must not raise.
    out = regenerate_global_report(tmp_path)
    assert out.exists()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_aggregate_report.py -k "regenerate_renders_suite or default_test_root" -q`
Expected: FAIL — `regenerate_global_report` takes no `test_root`; report not suite-grouped/catalog-less.

- [ ] **Step 3: Implement**

Replace `regenerate_global_report`:

```python
def regenerate_global_report(report_root: Path, test_root: Path | None = None) -> Path:
    report_root.mkdir(parents=True, exist_ok=True)
    if test_root is None:
        test_root = Path(__file__).resolve().parent.parent / "Test"
    entries = scan_runs(report_root)
    suite_groups = group_by_suite_then_date(entries)
    catalog = build_catalog(test_root, entries)
    html = render_html(suite_groups, catalog=catalog)
    out = report_root / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest test_aggregate_report.py -q`
Expected: PASS (all, including the older `test_regenerate_*` — they assert presence of `"tc01_foo"` / `"No test runs found"`, still true; default `test_root` may point at a real `../Test` but that only adds catalog content, doesn't remove report content).

- [ ] **Step 5: Commit**

```bash
git add aggregate_report.py test_aggregate_report.py
git commit -m "feat: render catalog + suite grouping in regenerate_global_report"
```

---

### Task 8: Shared `(suite, stem)` concurrency guard in `report_server.py`

Refactor the inline rerun guard into a reusable helper keyed on `(suite, stem)`, store `suite` on the job, and have `_handle_rerun` use it. This is the prerequisite for `/run` (Task 9) to share the guard.

**Files:**
- Modify: `report_server.py` (`_handle_rerun` ~173-234; add `_find_running_job`)
- Test: `test_rerun.py`

- [ ] **Step 1: Write the failing test**

```python
def test_find_running_job_keys_on_suite_and_stem(tmp_path):
    import report_server
    report_server._jobs.clear()
    import subprocess, sys, time
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    report_server._jobs["j1"] = {
        "job_id": "j1", "suite": "HeartSystem", "stem": "tc01",
        "proc": proc, "status": "running", "log_file": open(tmp_path / "j.log", "w"),
        "log_path": tmp_path / "j.log",
    }
    try:
        assert report_server._find_running_job("HeartSystem", "tc01") is not None
        assert report_server._find_running_job("DailyMission", "tc01") is None  # different suite
        assert report_server._find_running_job("HeartSystem", "tc02") is None   # different stem
    finally:
        proc.terminate()
        report_server._jobs.clear()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_rerun.py -k "find_running_job" -q`
Expected: FAIL — `_find_running_job` does not exist.

- [ ] **Step 3: Implement the helper**

Add to `report_server.py` (module level, after `_jobs`/`_jobs_lock`):

```python
def _find_running_job(suite: str, stem: str) -> dict | None:
    """Return a still-running job for (suite, stem), reaping any whose process
    already exited. Caller must hold _jobs_lock."""
    for job in _jobs.values():
        if job.get("suite") == suite and job["stem"] == stem and job["status"] == "running":
            rc = job["proc"].poll()
            if rc is None:
                return job
            # process exited but never reaped (client poller died) — reap it
            job["exit_code"] = rc
            job["status"] = "done" if rc == 0 else "failed"
            if "log_file" in job and not job["log_file"].closed:
                job["log_file"].close()
    return None
```

- [ ] **Step 4: Use it in `_handle_rerun` + store `suite`**

In `_handle_rerun`, after computing `stem = m.group(1)`, derive suite and use the helper. Replace the existing `with _jobs_lock:` guard loop (the `for job in _jobs.values(): if job["stem"] == stem ...` block) with:

```python
        suite = Path(air_path).parent.name or "unknown"
        with _jobs_lock:
            if _find_running_job(suite, stem) is not None:
                self._json(409, {"error": "already running"})
                return
            job_id = str(uuid.uuid4())
            # ... (existing log_path / log_file / Popen code unchanged) ...
```

And add `"suite": suite,` to the `_jobs[job_id] = {...}` dict.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest test_rerun.py -k "find_running_job or rerun" -q`
Expected: PASS — including the existing `test_rerun_concurrent_guard` (now suite-derived; the dummy `AIR_PATH` parent is `tc01_login.air` so suite is its parent dir name — still consistent for both POSTs to the same folder) and `test_rerun_reaps_stale_running_job`.

Note: `test_rerun_reaps_stale_running_job` injects a job dict WITHOUT a `suite` key; `_find_running_job` uses `.get("suite")` so it won't crash, but that stale job has `stem == "tc01_login"` and `suite == None`, while the rerun derives a real suite → they won't match, so the stale job won't be reaped by the guard. To keep that test's intent, add `"suite": Path(dummy_air).parent.name` to the injected dict in that test (line ~185).

- [ ] **Step 6: Commit**

```bash
git add report_server.py test_rerun.py
git commit -m "feat: shared (suite,stem) concurrency guard for reruns"
```

---

### Task 9: `POST /run` endpoint with path confinement

**Files:**
- Modify: `report_server.py` (`do_POST` routing ~84-145; add `_handle_run`; add `TEST_ROOT` + `PROJECT_ROOT` constants near top)
- Test: `test_rerun.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_run_rejects_path_outside_test_root(tmp_path):
    server, _ = _make_test_server(tmp_path, 17081)
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:17081/run", method="POST",
            data=json.dumps({"air_path": "../../etc/passwd"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as r:
                status, body = r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read())
        assert status == 400
        assert "error" in body
    finally:
        server.shutdown()


def test_run_rejects_non_air(tmp_path, monkeypatch):
    import report_server
    monkeypatch.setattr(report_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(report_server, "TEST_ROOT", (tmp_path / "Test").resolve())
    (tmp_path / "Test" / "HeartSystem").mkdir(parents=True)
    (tmp_path / "Test" / "HeartSystem" / "tc01.txt").write_text("x", encoding="utf-8")
    server, _ = _make_test_server(tmp_path, 17082)
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:17082/run", method="POST",
            data=json.dumps({"air_path": "Test/HeartSystem/tc01.txt"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as r:
                status, body = r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read())
        assert status == 400
    finally:
        server.shutdown()


def test_run_accepts_valid_air_returns_job_id(tmp_path, monkeypatch):
    import report_server
    monkeypatch.setattr(report_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(report_server, "TEST_ROOT", (tmp_path / "Test").resolve())
    air = tmp_path / "Test" / "HeartSystem" / "tc01_a.air"
    air.parent.mkdir(parents=True)
    air.mkdir()  # .air is a directory containing a .py (matches dagster layout)
    (air / "tc01_a.py").write_text("def main(): pass\n", encoding="utf-8")
    server, _ = _make_test_server(tmp_path, 17083)
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:17083/run", method="POST",
            data=json.dumps({"air_path": "Test/HeartSystem/tc01_a.air"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            status, body = r.status, json.loads(r.read())
        assert status == 200
        assert len(body["job_id"]) == 36
    finally:
        with report_server._jobs_lock:
            for job in report_server._jobs.values():
                try: job["proc"].terminate()
                except Exception: pass
        server.shutdown()
```

Note: `.air` is a **directory** in this codebase (the guard must accept dirs, not just files — see Step 3). The valid-path test reflects that.

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest test_rerun.py -k "test_run_" -q`
Expected: FAIL — `/run` route returns 405 (unhandled).

- [ ] **Step 3: Add constants + `_handle_run` + route**

Near the top of `report_server.py`, after `_project_root` is defined (~line 25), add module constants:

```python
PROJECT_ROOT = _project_root
TEST_ROOT = (_project_root / "Test").resolve()
```

Add the route in `do_POST` (before the final `405`):

```python
        if self.path == "/run":
            self._handle_run()
            return
```

Add the handler. `.air` entries are directories in this repo, so accept a file **or** dir whose suffix is `.air`:

```python
    def _handle_run(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            air_path = payload.get("air_path", "")
        except (ValueError, OSError):
            self._json(400, {"error": "bad request body"})
            return
        if not air_path:
            self._json(400, {"error": "air_path required"})
            return
        p = (PROJECT_ROOT / air_path).resolve()
        if not (p.exists() and p.suffix == ".air" and TEST_ROOT in p.parents):
            self._json(400, {"error": "path must be an existing .air under Test/"})
            return
        suite = p.parent.name or "unknown"
        stem = p.stem
        with _jobs_lock:
            if _find_running_job(suite, stem) is not None:
                self._json(409, {"error": "already running"})
                return
            job_id = str(uuid.uuid4())
            log_path = REPORT_ROOT / f"{job_id}.log"
            log_file = log_path.open("w", encoding="utf-8")
            dagster_run = Path(__file__).parent / "dagster_run.py"
            import os
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", str(dagster_run), str(p)],
                    stdout=log_file, stderr=subprocess.STDOUT, env=env,
                )
            except FileNotFoundError:
                log_file.close()
                self._json(500, {"error": "dagster_run.py not found"})
                return
            _jobs[job_id] = {
                "job_id": job_id, "suite": suite, "stem": stem,
                "air_path": str(p), "proc": proc, "status": "running",
                "new_folder": None, "exit_code": None, "started": time.time(),
                "log_file": log_file, "log_path": log_path,
            }
        self._json(200, {"job_id": job_id})
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest test_rerun.py -k "test_run_" -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the FULL test suite**

Run: `python -m pytest test_aggregate_report.py test_rerun.py -q`
Expected: PASS (all).

- [ ] **Step 6: Manual smoke (optional, needs a device)**

Run: `python report_server.py` from `dagster/`, open `http://localhost:7070/`, click **Test Catalog**, pick a suite, click **▶ Run** on a test, confirm live logs stream and status resolves to ✓/✗.

- [ ] **Step 7: Commit**

```bash
git add report_server.py test_rerun.py
git commit -m "feat: POST /run endpoint to launch any Test/ case from catalog"
```

---

## Self-Review

**Spec coverage:**
- Catalog browse of `../Test/` incl. never-run → Task 3 (`scan_catalog`) + Task 4 (`build_catalog`) + Task 6 (catalog render). ✓
- Start fresh test (Run button) → Task 9 (`/run`) + Task 6 (`runCatalogTest`). ✓
- Live monitor (log text) → Task 6 reuses `pollRerunStatus` / `/rerun-logs`. ✓
- Report grouped suite → day → runs (replace) → Task 2 + Task 5 + Task 7. ✓
- `suite` field crux → Task 1. ✓
- `unknown` bucket → Task 1 (`extract_suite` returns "unknown") + Task 2 (sorts last). ✓
- `/run` path confinement → Task 9. ✓
- Shared `(suite,stem)` concurrency guard → Task 8 + reused in Task 9. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `RunEntry.suite` (Task 1) used by `group_by_suite_then_date` (2), `build_catalog` (4). `render_html(suite_groups, catalog=...)` signature (5/6) matches `regenerate_global_report` call (7). Catalog test dict keys `stem/air_path/last_status/last_href` consistent across Tasks 4 & 6. Job dict `suite` key added in Tasks 8 & 9, read by `_find_running_job` (8). ✓
