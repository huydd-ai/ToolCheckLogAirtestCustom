# Backend Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three issues found in the senior backend review: dev mode runs invisible to global report, double-wrapped exceptions in `generate_html`, and status determination order in `run_single_test`.

**Architecture:** Three independent one-file changes: (1) remove mode guard from `write_log_txt` call in `runner.py` so log.txt is always written; (2) remove the inner `try/except` from `generate_html` in `reporting.py` since the caller already wraps it; (3) hoist final status computation before `write_log_txt` call in `runner.py` so both consumers see the same value. No new files required.

**Tech Stack:** Python stdlib. Pytest for test additions. No new deps.

---

## Context

Three independent bugs/smells found by a backend code review:

### Bug 1 — Dev mode runs invisible to aggregate report
`runner.py:73` guards `write_log_txt` with `if mode == "tester"`. Dev mode never writes `log.txt`. `aggregate_report.scan_runs()` skips folders without `log.txt` (treats them as in-progress). Dev runs are silently absent from `report_run/report.html`.

### Smell 2 — Double-wrapped exceptions in `generate_html`
`reporting.py:133` wraps everything in `try/except Exception` and prints a WARN. `runner.py:70` also wraps the `generate_html` call in `try/except`. The outer wrapper renders the inner one redundant and it hides the real exception from the outer handler's context.

### Smell 3 — Status re-check AFTER `write_log_txt`
`runner.py:75` calls `write_log_txt` (which independently computes status from steps). Then `runner.py:81` re-checks steps to potentially flip `status` to FAIL. Both compute the same thing, but the intent is not obvious and future changes could cause divergence. Compute final status once, before calling `write_log_txt`.

---

## File Structure

**Modify only:**
- `dagster/runner.py` — Tasks 1 and 3 (mode guard removal, status hoisting)
- `dagster/reporting.py` — Task 2 (remove inner try/except)

**Add tests to:**
- `dagster/test_reporting.py` — Task 2 verification

**Unit testing note for `runner.py`:** `run_single_test` has hard Airtest+device dependencies; it cannot be unit tested in isolation. Changes are verified by: (a) existing `test_reporting.py` coverage of `write_log_txt`; (b) existing `test_aggregate_report.py` verifying `scan_runs` picks up log.txt; (c) manual smoke test.

---

## Task 1: Fix dev mode log.txt bug

**Files:**
- Modify: `dagster/runner.py:73-78`

The fix removes the `if mode == "tester":` guard so `write_log_txt` is always called.

Current code (`runner.py:73-78`):
```python
        if mode == "tester":
            try:
                write_log_txt(out_dir, air_path.stem, get_steps(), error_top)
                print(f"[INFO] log.txt written with {len(get_steps())} steps")
            except Exception as e:
                print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)
```

- [ ] **Step 1: Verify existing test catches scan behavior**

Run:
```
cd D:\AutoRebase\dagster
python -m pytest test_aggregate_report.py::test_scan_runs_skips_in_progress_without_status -v
```
Expected: PASS — confirms `scan_runs` skips folders without `log.txt`.

- [ ] **Step 2: Apply fix**

Edit `dagster/runner.py`. Replace lines 73-78 with:
```python
        try:
            write_log_txt(out_dir, air_path.stem, get_steps(), error_top)
            print(f"[INFO] log.txt written with {len(get_steps())} steps")
        except Exception as e:
            print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)
```

- [ ] **Step 3: Run full test suite**

```
python -m pytest test_reporting.py test_aggregate_report.py test_parallel_utils.py -v
```
Expected: all 56 tests pass.

- [ ] **Step 4: Commit**

```bash
git add dagster/runner.py
git commit -m "fix(dagster): write log.txt in dev mode so global report captures dev runs"
```

---

## Task 2: Remove redundant inner try/except from `generate_html`

**Files:**
- Modify: `dagster/reporting.py:131-163`
- Test: `dagster/test_reporting.py`

`generate_html` currently swallows every exception and prints a WARN. This hides errors from the caller, which already wraps the call in `try/except` (`runner.py:70`). Removing the inner wrapper lets the actual exception propagate to the caller's handler, which prints its own WARN. Behaviour is identical for the user (WARN printed, run continues); internals are cleaner.

- [ ] **Step 1: Write a test verifying `generate_html` propagates on airtest import failure**

Append to `dagster/test_reporting.py`:
```python
import importlib
import sys


def test_generate_html_propagates_exception_on_missing_airtest(tmp_path, monkeypatch):
    """generate_html should raise when LogToHtml import fails — caller handles it."""
    # Simulate airtest.report.report not importable
    monkeypatch.setitem(sys.modules, "airtest.report.report", None)

    from reporting import generate_html

    air_path = tmp_path / "tc01.air"
    air_path.mkdir()

    import pytest
    with pytest.raises(Exception):
        generate_html(air_path, tmp_path, "tester")
```

- [ ] **Step 2: Run test — expect FAIL (current code swallows exception)**

```
python -m pytest test_reporting.py::test_generate_html_propagates_exception_on_missing_airtest -v
```
Expected: FAIL — current `generate_html` catches the ImportError and returns silently, so `pytest.raises(Exception)` sees no exception → AssertionError.

- [ ] **Step 3: Remove inner try/except from `generate_html`**

Edit `dagster/reporting.py`. Replace:
```python
def generate_html(air_path: Path, out_dir: Path, mode: str, ndjson_name: str = "airtest.log", recordings: list[Path] | None = None) -> None:
    """Generate Airtest HTML report from NDJSON log."""
    try:
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
            redirect_rel = f"{exported.name}/{target_report.name}"
            (out_dir / "report.html").write_text(
                "<!DOCTYPE html><meta charset=\"utf-8\">"
                f"<meta http-equiv=\"refresh\" content=\"0; url={redirect_rel}\">"
                "<title>Redirecting...</title>"
                f"<p>If you are not redirected, <a href=\"{redirect_rel}\">click here</a>.</p>",
                encoding="utf-8",
            )
    except Exception as e:
        print(f"[WARN] Failed to generate HTML report: {e}", file=sys.stderr)
```

With:
```python
def generate_html(air_path: Path, out_dir: Path, mode: str, ndjson_name: str = "airtest.log", recordings: list[Path] | None = None) -> None:
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
        redirect_rel = f"{exported.name}/{target_report.name}"
        (out_dir / "report.html").write_text(
            "<!DOCTYPE html><meta charset=\"utf-8\">"
            f"<meta http-equiv=\"refresh\" content=\"0; url={redirect_rel}\">"
            "<title>Redirecting...</title>"
            f"<p>If you are not redirected, <a href=\"{redirect_rel}\">click here</a>.</p>",
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run new test — expect PASS**

```
python -m pytest test_reporting.py::test_generate_html_propagates_exception_on_missing_airtest -v
```
Expected: PASS.

- [ ] **Step 5: Run full test suite**

```
python -m pytest test_reporting.py test_aggregate_report.py test_parallel_utils.py -v
```
Expected: all 57 tests pass.

- [ ] **Step 6: Commit**

```bash
git add dagster/reporting.py dagster/test_reporting.py
git commit -m "fix(dagster): remove redundant inner try/except from generate_html, let caller handle"
```

---

## Task 3: Hoist final status computation before `write_log_txt`

**Files:**
- Modify: `dagster/runner.py:37-86`

Currently `write_log_txt` is called (which computes status internally from steps+error_top), then `status` is re-checked again at line 81. Both produce the same result but it is unclear and fragile. Extract a `final_status` once before calling `write_log_txt`, use it for both the RESULT print and avoid the redundant re-check.

Current `runner.py` finally block (lines 53-86):
```python
    finally:
        if recorder:
            try:
                recorder.stop()
            except Exception as e:
                print(f"[WARN] recorder stop: {e}", file=sys.stderr)
        sys.path.remove(str(air_path))

        try:
            G.LOGGER.set_logfile(None)
        except Exception:
            pass

        try:
            recordings = sorted(out_dir.glob("recording_*.mp4"))
            generate_html(air_path, out_dir, mode, ndjson_name="airtest.log", recordings=recordings)
            print(f"[INFO] report.html generated")
        except Exception as e:
            print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

        try:
            write_log_txt(out_dir, air_path.stem, get_steps(), error_top)
            print(f"[INFO] log.txt written with {len(get_steps())} steps")
        except Exception as e:
            print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)

        print(f"Report: {out_dir}")
        if status == "PASS" and any(s["status"] == "FAIL" for s in get_steps()):
            status = "FAIL"
            
        print(f"[RESULT]\t{module_name}\t{status}\t{out_dir}")
```

- [ ] **Step 1: Verify no test covers runner status logic**

```
python -m pytest -v -k "status" 2>&1 | head -20
```
Expected: no runner-specific status tests (confirming we're adding coverage, not breaking existing tests).

- [ ] **Step 2: Apply the refactor**

Edit `dagster/runner.py`. Replace the `finally` block above with:
```python
    finally:
        if recorder:
            try:
                recorder.stop()
            except Exception as e:
                print(f"[WARN] recorder stop: {e}", file=sys.stderr)
        sys.path.remove(str(air_path))

        try:
            G.LOGGER.set_logfile(None)
        except Exception:
            pass

        # Compute final status once from captured steps; covers the case where
        # main() completed without exception but individual steps still failed.
        steps = get_steps()
        if status == "PASS" and any(s["status"] == "FAIL" for s in steps):
            status = "FAIL"

        try:
            recordings = sorted(out_dir.glob("recording_*.mp4"))
            generate_html(air_path, out_dir, mode, ndjson_name="airtest.log", recordings=recordings)
            print(f"[INFO] report.html generated")
        except Exception as e:
            print(f"[WARN] Failed to generate report: {e}", file=sys.stderr)

        try:
            write_log_txt(out_dir, air_path.stem, steps, error_top)
            print(f"[INFO] log.txt written with {len(steps)} steps")
        except Exception as e:
            print(f"[WARN] Failed to write log.txt: {e}", file=sys.stderr)

        print(f"Report: {out_dir}")
        print(f"[RESULT]\t{module_name}\t{status}\t{out_dir}")
```

- [ ] **Step 3: Run full test suite**

```
python -m pytest test_reporting.py test_aggregate_report.py test_parallel_utils.py -v
```
Expected: all 57 tests pass.

- [ ] **Step 4: Commit**

```bash
git add dagster/runner.py
git commit -m "refactor(dagster): hoist final status computation before write_log_txt to eliminate redundant re-check"
```

---

## Verification Summary

| Fix | How to verify |
|-----|---------------|
| Dev mode log.txt | Run any test in dev mode (`--mode dev`), confirm `report_run/<stem>_<ts>/log.txt` exists and contains `# Status:` line |
| Exception propagation | `pytest test_reporting.py::test_generate_html_propagates_exception_on_missing_airtest` |
| Status hoisting | Full suite green + manual smoke: run a test where main() passes but a step inside fails — confirm `[RESULT]` prints FAIL and log.txt also says FAIL |
| No regression | `pytest test_reporting.py test_aggregate_report.py test_parallel_utils.py` — 57 passed |
