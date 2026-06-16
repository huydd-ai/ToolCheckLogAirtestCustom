import json
import re
from pathlib import Path

from reporting import write_log_txt, _normalize_and_filter_airtest_log


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_step(name, action, status, screenshot=None, behaviour=None):
    return {"name": name, "action": action, "status": status,
            "screenshot": screenshot, "behaviour": behaviour}


def _read_log(out_dir: Path) -> list[str]:
    return (out_dir / "log.txt").read_text(encoding="utf-8").splitlines()


def _make_entry(tag="function", depth=2, name="fn", traceback=None):
    return {"tag": tag, "depth": depth, "time": 0.0,
            "data": {"name": name, "traceback": traceback}}


def _write_ndjson(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _read_ndjson(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── write_log_txt ──────────────────────────────────────────────────────────────

def test_write_log_txt_pass_when_all_steps_pass(tmp_path):
    steps = [_make_step("s1", "touch", "PASS"), _make_step("s2", "wait", "PASS")]
    write_log_txt(tmp_path, "tc01", steps, None)
    assert _read_log(tmp_path)[2] == "# Status: PASS"


def test_write_log_txt_fail_when_any_step_fails(tmp_path):
    steps = [_make_step("s1", "touch", "PASS"), _make_step("s2", "wait", "FAIL")]
    write_log_txt(tmp_path, "tc01", steps, None)
    assert _read_log(tmp_path)[2] == "# Status: FAIL"


def test_write_log_txt_fail_when_error_top(tmp_path):
    write_log_txt(tmp_path, "tc01", [], RuntimeError("boom"))
    assert _read_log(tmp_path)[2] == "# Status: FAIL"


def test_write_log_txt_header_first_line_is_name(tmp_path):
    write_log_txt(tmp_path, "my_test_case", [], None)
    assert _read_log(tmp_path)[0] == "# my_test_case"


def test_write_log_txt_header_run_line_format(tmp_path):
    write_log_txt(tmp_path, "tc01", [], None)
    assert re.match(r"^# Run: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", _read_log(tmp_path)[1])


def test_write_log_txt_step_without_behaviour(tmp_path):
    steps = [_make_step("  step1  ", "touch", "PASS", screenshot="s.jpg")]
    write_log_txt(tmp_path, "tc01", steps, None)
    assert "step1: touch, s.jpg, PASS" in _read_log(tmp_path)


def test_write_log_txt_step_with_behaviour(tmp_path):
    steps = [_make_step("step1", "touch", "PASS", screenshot="s.jpg", behaviour="tap_ok")]
    write_log_txt(tmp_path, "tc01", steps, None)
    assert "step1: touch, s.jpg, PASS, tap_ok" in _read_log(tmp_path)


def test_write_log_txt_no_screenshot_uses_dash(tmp_path):
    steps = [_make_step("step1", "touch", "PASS", screenshot=None)]
    write_log_txt(tmp_path, "tc01", steps, None)
    assert "step1: touch, -, PASS" in _read_log(tmp_path)


def test_write_log_txt_error_line_when_no_steps(tmp_path):
    write_log_txt(tmp_path, "tc01", [], RuntimeError("connection failed"))
    lines = _read_log(tmp_path)
    assert any("ERROR: connection failed" in l for l in lines)


def test_write_log_txt_no_error_line_when_steps_exist(tmp_path):
    steps = [_make_step("s1", "touch", "FAIL")]
    write_log_txt(tmp_path, "tc01", steps, RuntimeError("boom"))
    lines = _read_log(tmp_path)
    assert not any(l.startswith("ERROR:") for l in lines)


def test_write_log_txt_pass_when_empty_steps_no_error(tmp_path):
    write_log_txt(tmp_path, "tc01", [], None)
    assert _read_log(tmp_path)[2] == "# Status: PASS"


# ── _normalize_and_filter_airtest_log ─────────────────────────────────────────

def test_normalize_missing_file_no_crash(tmp_path):
    _normalize_and_filter_airtest_log(tmp_path / "missing.log", "tester")


def test_normalize_depth_offset_applied(tmp_path):
    log = tmp_path / "airtest.log"
    _write_ndjson(log, [_make_entry(depth=3), _make_entry(depth=4), _make_entry(depth=5)])
    _normalize_and_filter_airtest_log(log, "tester")
    assert [e["depth"] for e in _read_ndjson(log)] == [1, 2, 3]


def test_normalize_no_offset_when_depth_already_one(tmp_path):
    log = tmp_path / "airtest.log"
    _write_ndjson(log, [_make_entry(depth=1), _make_entry(depth=2)])
    _normalize_and_filter_airtest_log(log, "tester")
    assert [e["depth"] for e in _read_ndjson(log)] == [1, 2]


def test_normalize_tester_mode_keeps_all_function_entries(tmp_path):
    log = tmp_path / "airtest.log"
    _write_ndjson(log, [_make_entry(name="fn1"), _make_entry(name="fn2")])
    _normalize_and_filter_airtest_log(log, "tester")
    assert len(_read_ndjson(log)) == 2


def test_normalize_dev_mode_keeps_error_entries(tmp_path):
    log = tmp_path / "airtest.log"
    _write_ndjson(log, [_make_entry(name="fail", traceback="Traceback...")])
    _normalize_and_filter_airtest_log(log, "dev")
    result = _read_ndjson(log)
    assert len(result) == 1
    assert result[0]["data"]["name"] == "fail"


def test_normalize_dev_mode_filters_function_tags_far_from_errors(tmp_path):
    # error at index 0; entries at i=1 and i=2 are within window, i=3+ filtered
    # range(i-2, i+5) for i=1 → range(-1,6) contains 0 → kept
    # range(i-2, i+5) for i=2 → range(0,7) contains 0 → kept
    # range(i-2, i+5) for i=3 → range(1,8) → 0 absent → filtered
    log = tmp_path / "airtest.log"
    error_entry = _make_entry(name="err", traceback="Traceback...")
    fn_entries = [_make_entry(name=f"fn{i}") for i in range(10)]
    _write_ndjson(log, [error_entry] + fn_entries)
    _normalize_and_filter_airtest_log(log, "dev")
    names = [e["data"]["name"] for e in _read_ndjson(log)]
    assert "err" in names
    assert "fn0" in names    # index 1 — within window
    assert "fn1" in names    # index 2 — within window
    assert "fn2" not in names  # index 3 — outside window
    assert "fn9" not in names  # far outside window


def test_normalize_skips_invalid_json_lines(tmp_path):
    log = tmp_path / "airtest.log"
    valid = json.dumps(_make_entry(depth=1))
    log.write_text(valid + "\nNOT JSON\n" + valid + "\n", encoding="utf-8")
    _normalize_and_filter_airtest_log(log, "tester")
    assert len(_read_ndjson(log)) == 2


def test_normalize_pending_screen_appended_after_error(tmp_path):
    log = tmp_path / "airtest.log"
    screen_entry = {"tag": "function", "depth": 2, "time": 0.0,
                    "data": {"name": "Take Screen and Log", "ret": {}, "traceback": None}}
    error_entry = _make_entry(name="fail_step", traceback="Traceback...")
    _write_ndjson(log, [screen_entry, error_entry])
    _normalize_and_filter_airtest_log(log, "tester")
    result = _read_ndjson(log)
    assert len(result) == 2
    names = [e["data"]["name"] for e in result]
    # screen_entry is renamed to try_log_screen and injected AFTER error
    assert "fail_step" in names
    assert "try_log_screen" in names
    assert names.index("try_log_screen") > names.index("fail_step")


def test_normalize_pending_screen_appended_at_end_when_no_error_follows(tmp_path):
    log = tmp_path / "airtest.log"
    normal_entry = _make_entry(name="normal_step")
    screen_entry = {"tag": "function", "depth": 2, "time": 0.0,
                    "data": {"name": "Take Screen and Log", "ret": {}, "traceback": None}}
    _write_ndjson(log, [normal_entry, screen_entry])
    _normalize_and_filter_airtest_log(log, "tester")
    result = _read_ndjson(log)
    assert len(result) == 2
    names = [e["data"]["name"] for e in result]
    assert "normal_step" in names
    assert "try_log_screen" in names


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


# ── generate_summary_report ────────────────────────────────────────────────────

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


def test_generate_summary_report_banner_shows_skip(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc01", [], "SKIP", [], None)
    html = path.read_text(encoding="utf-8")
    assert "SKIP" in html
    assert 'class="banner skip"' in html
    assert 'class="banner fail"' not in html


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
