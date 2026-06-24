import re
from pathlib import Path

from reporting import write_log_txt


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_step(name, action, status, screenshot=None, behaviour=None):
    return {"name": name, "action": action, "status": status,
            "screenshot": screenshot, "behaviour": behaviour}


def _read_log(out_dir: Path) -> list[str]:
    return (out_dir / "log.txt").read_text(encoding="utf-8").splitlines()


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


# ── generate_summary_report ────────────────────────────────────────────────────

def test_generate_summary_report_writes_file(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.5}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    assert path.exists()
    assert path.name == "report.html"


def test_generate_summary_report_banner_shows_pass(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.5}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "PASS" in html
    assert "pass" in html.lower()


def test_generate_summary_report_banner_shows_fail(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "FAIL", "screenshot": None, "behaviour": "Error", "duration": 2.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "FAIL", [], None)
    html = path.read_text(encoding="utf-8")
    assert "FAIL" in html
    assert "fail" in html.lower()


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
    """End-to-end smoke: function callable with the same args runner.py passes."""
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc_integration", [], "PASS", [], None)
    assert path.exists()
    html = path.read_text(encoding="utf-8")
    assert "PASS" in html
    assert "tc_integration" in html


def test_generate_summary_report_empty_steps_shows_no_steps_message(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc01", [], "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert "No steps captured" in html
    assert 'class="no-runs"' in html


def test_generate_summary_report_renders_error_panel_from_error_top(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc01", [], "FAIL", [], RuntimeError("connection refused"))
    html = path.read_text(encoding="utf-8")
    assert "Failure detail" in html
    assert "connection refused" in html
    assert "error-panel" in html


def test_generate_summary_report_renders_error_panel_from_first_fail_step(tmp_path):
    from reporting import generate_summary_report
    steps = [
        {"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0},
        {"name": "s2", "action": "wait", "status": "FAIL", "screenshot": "shot.jpg", "behaviour": "timeout 30s", "duration": 30.0},
        {"name": "s3", "action": "touch", "status": "FAIL", "screenshot": "shot2.jpg", "behaviour": "later fail", "duration": 1.0},
    ]
    path = generate_summary_report(tmp_path, "tc01", steps, "FAIL", [], None)
    html = path.read_text(encoding="utf-8")
    assert "Failure detail" in html
    assert "timeout 30s" in html
    # First fail's screenshot rendered both as thumbnail in table and full-size in panel
    assert html.count("shot.jpg") >= 2
    # Later-fail message NOT in error panel (only first fail used)
    assert "later fail" in html  # still appears in table row
    panel_html = html.split('class="error-panel"', 1)[1]
    assert "later fail" not in panel_html


def test_generate_summary_report_no_error_panel_on_pass_only(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert '<div class="error-panel">' not in html
    assert "Failure detail" not in html


def test_generate_summary_report_multiple_recording_badges(tmp_path):
    from reporting import generate_summary_report
    r1 = tmp_path / "recording_dev1_tc01.mp4"
    r2 = tmp_path / "recording_dev2_tc01.mp4"
    r1.write_text("a")
    r2.write_text("b")
    path = generate_summary_report(tmp_path, "tc01", [], "PASS", [r1, r2], None)
    html = path.read_text(encoding="utf-8")
    assert html.count("rec-badge") >= 2
    assert "recording_dev1_tc01.mp4" in html
    assert "recording_dev2_tc01.mp4" in html


def test_generate_summary_report_escapes_status_parameter(tmp_path):
    from reporting import generate_summary_report
    path = generate_summary_report(tmp_path, "tc01", [], "<x>", [], None)
    html = path.read_text(encoding="utf-8")
    assert "<x>" not in html
    assert "&lt;x&gt;" in html


def test_generate_summary_report_unknown_step_status_treated_as_fail(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "s1", "action": "touch", "status": "WAT", "screenshot": None, "behaviour": None, "duration": 1.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "FAIL", [], None)
    html = path.read_text(encoding="utf-8")
    assert "status-badge fail" in html
    assert ">WAT<" not in html  # raw status not emitted; coerced to FAIL
    assert ">FAIL<" in html


def test_generate_summary_report_step_name_has_class_for_search(tmp_path):
    from reporting import generate_summary_report
    steps = [{"name": "find me", "action": "touch", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0}]
    path = generate_summary_report(tmp_path, "tc01", steps, "PASS", [], None)
    html = path.read_text(encoding="utf-8")
    assert 'class="step-name">find me<' in html
