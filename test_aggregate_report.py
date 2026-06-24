from datetime import datetime
from pathlib import Path

from aggregate_report import (
    parse_run_folder_name,
    extract_status,
    RunEntry,
    scan_runs,
    group_by_date,
    group_by_suite_then_date,
    render_html,
    regenerate_global_report,
)


def test_parse_simple_stem():
    assert parse_run_folder_name("tc01_foo_20260612_102041") == (
        "tc01_foo",
        datetime(2026, 6, 12, 10, 20, 41),
    )


def test_parse_stem_with_underscores():
    assert parse_run_folder_name(
        "tc01_check_daily_mission_icon_before_and_after_unlock_20260612_102041"
    ) == (
        "tc01_check_daily_mission_icon_before_and_after_unlock",
        datetime(2026, 6, 12, 10, 20, 41),
    )


def test_parse_non_matching_returns_none():
    assert parse_run_folder_name("_parallel_20260612_102041") is None
    assert parse_run_folder_name("random_folder") is None
    assert parse_run_folder_name("tc01_foo_20260612") is None


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_extract_status_pass(tmp_path):
    log = _write(tmp_path, "log.txt", "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: PASS\n")
    assert extract_status(log) == "PASS"


def test_extract_status_fail(tmp_path):
    log = _write(tmp_path, "log.txt", "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: FAIL\n")
    assert extract_status(log) == "FAIL"


def test_extract_status_skip(tmp_path):
    log = _write(tmp_path, "log.txt", "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: SKIP\n")
    assert extract_status(log) == "SKIP"


def test_extract_status_missing_returns_unknown(tmp_path):
    log = _write(tmp_path, "log.txt", "no status line here\n")
    assert extract_status(log) == "UNKNOWN"


def test_extract_status_file_absent(tmp_path):
    assert extract_status(tmp_path / "missing.txt") == "UNKNOWN"


def _make_run(root: Path, folder: str, status_line: str | None) -> Path:
    d = root / folder
    d.mkdir()
    if status_line is not None:
        (d / "log.txt").write_text(
            f"# stem\n# Run: 2026-06-12 10:00:00\n{status_line}\n",
            encoding="utf-8",
        )
    return d


def test_scan_runs_finds_matching_folders(tmp_path):
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")
    _make_run(tmp_path, "tc02_bar_20260612_103000", "# Status: FAIL")
    entries = scan_runs(tmp_path)
    assert len(entries) == 2
    stems = {e.stem for e in entries}
    assert stems == {"tc01_foo", "tc02_bar"}


def test_scan_runs_skips_non_matching(tmp_path):
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")
    _make_run(tmp_path, "_parallel_20260612_102041", "# Status: PASS")
    (tmp_path / "random_dir").mkdir()
    entries = scan_runs(tmp_path)
    assert len(entries) == 1
    assert entries[0].stem == "tc01_foo"


def test_scan_runs_skips_in_progress_without_status(tmp_path):
    d = _make_run(tmp_path, "tc01_foo_20260612_102041", None)
    (d / "airtest.log").write_text("", encoding="utf-8")
    entries = scan_runs(tmp_path)
    assert entries == []


def test_scan_runs_relative_report_path(tmp_path):
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")
    entries = scan_runs(tmp_path)
    assert entries[0].report_href == "tc01_foo_20260612_102041/report.html"


def test_scan_runs_empty_root(tmp_path):
    assert scan_runs(tmp_path) == []


def _entry(stem: str, dt_str: str, status: str) -> RunEntry:
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    folder = f"{stem}_{dt.strftime('%Y%m%d_%H%M%S')}"
    return RunEntry(stem, dt, status, folder, f"{folder}/report.html")


def test_group_by_date_dates_sorted_descending():
    entries = [
        _entry("a", "2026-06-10 10:00:00", "PASS"),
        _entry("b", "2026-06-12 10:00:00", "PASS"),
        _entry("c", "2026-06-11 10:00:00", "PASS"),
    ]
    groups = group_by_date(entries)
    assert [d for d, _ in groups] == ["2026-06-12", "2026-06-11", "2026-06-10"]


def test_group_by_date_within_group_sorted_newest_first():
    entries = [
        _entry("a", "2026-06-12 09:00:00", "PASS"),
        _entry("b", "2026-06-12 11:30:00", "FAIL"),
        _entry("c", "2026-06-12 10:00:00", "PASS"),
    ]
    groups = group_by_date(entries)
    assert len(groups) == 1
    _, rows = groups[0]
    assert [r.stem for r in rows] == ["b", "c", "a"]


def test_group_by_date_empty():
    assert group_by_date([]) == []


def test_render_html_contains_doctype_and_title():
    html = render_html([])
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>Dagster Test Reports</title>" in html


def test_render_html_empty_state():
    html = render_html([])
    assert "No test runs found" in html


def test_render_html_inline_assets():
    # Dashboard ships self-contained: inline <style> + inline JS, no external files.
    html = render_html([])
    assert "<style>" in html
    assert "function openReport(" in html


def test_render_html_group_header_has_counts():
    entries = [
        _entry("a", "2026-06-12 10:00:00", "PASS"),
        _entry("b", "2026-06-12 11:00:00", "FAIL"),
        _entry("c", "2026-06-12 09:00:00", "PASS"),
    ]
    html = render_html(group_by_suite_then_date(entries))
    assert "2026-06-12" in html
    assert "2 PASS" in html
    assert "1 FAIL" in html


def test_render_html_today_open_past_collapsed():
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday_entries = [_entry("a", "2020-01-01 10:00:00", "PASS")]
    today_entries = [_entry("b", datetime.now().strftime("%Y-%m-%d 10:00:00"), "PASS")]
    html = render_html(group_by_suite_then_date(today_entries + yesterday_entries))
    assert "<details open>" in html   # today expanded
    assert "<details>" in html        # past day collapsed
    assert today in html


def test_render_html_row_links_to_report():
    entries = [_entry("tc01_foo", "2026-06-12 10:20:41", "PASS")]
    html = render_html(group_by_suite_then_date(entries))
    assert 'href="tc01_foo_20260612_102041/report.html"' in html
    assert "tc01_foo" in html


def test_render_html_status_badge_classes():
    entries = [
        _entry("a", "2026-06-12 10:00:00", "PASS"),
        _entry("b", "2026-06-12 11:00:00", "FAIL"),
        _entry("c", "2026-06-12 09:00:00", "SKIP"),
    ]
    html = render_html(group_by_suite_then_date(entries))
    assert 'class="badge pass">PASS<' in html
    assert 'class="badge fail">FAIL<' in html
    assert 'class="badge skip">SKIP<' in html


def test_render_html_escapes_stem():
    entries = [_entry("tc01_<script>", "2026-06-12 10:00:00", "PASS")]
    html = render_html(group_by_suite_then_date(entries))
    assert "tc01_<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_summary_bar_metrics():
    entries = [
        _entry("a", "2026-06-12 10:00:00", "PASS"),
        _entry("b", "2026-06-12 11:00:00", "FAIL"),
        _entry("c", "2026-06-12 09:00:00", "PASS"),
    ]
    html = render_html(group_by_suite_then_date(entries))
    assert 'class="summary-bar"' in html
    assert "Pass rate" in html
    assert "67%" in html  # round(100 * 2 / 3)


def test_render_html_filter_controls():
    html = render_html(group_by_suite_then_date([_entry("a", "2026-06-12 10:00:00", "PASS")]))
    assert 'id="dash-search"' in html
    assert 'class="filter-pill active" data-status="all"' in html
    assert 'data-status="pass"' in html


def test_render_html_run_item_filter_attrs():
    entries = [_entry("tc01_foo", "2026-06-12 10:20:41", "PASS")]
    html = render_html(group_by_suite_then_date(entries))
    assert 'data-name="tc01_foo"' in html
    assert 'class="run-item" data-status="pass"' in html


def test_regenerate_writes_report_html(tmp_path):
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")
    out = regenerate_global_report(tmp_path)
    assert out == tmp_path / "report.html"
    assert out.exists()
    assert "tc01_foo" in out.read_text(encoding="utf-8")


def test_regenerate_overwrites_existing(tmp_path):
    (tmp_path / "report.html").write_text("OLD", encoding="utf-8")
    _make_run(tmp_path, "tc01_foo_20260612_102041", "# Status: PASS")
    regenerate_global_report(tmp_path)
    assert "OLD" not in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_regenerate_empty_root_writes_empty_state(tmp_path):
    out = regenerate_global_report(tmp_path)
    assert out.exists()
    assert "No test runs found" in out.read_text(encoding="utf-8")


def test_regenerate_creates_root_if_missing(tmp_path):
    target = tmp_path / "report_run"
    out = regenerate_global_report(target)
    assert out.exists()
    assert target.exists()


def test_render_html_group_has_delete_all_button():
    entries = [_entry("a", "2026-06-12 10:00:00", "PASS")]
    html = render_html(group_by_suite_then_date(entries))
    assert 'class="delete-all-btn"' in html
    assert "deleteAllRuns(this, '2026-06-12')" in html


def test_render_html_row_has_delete_button():
    entries = [_entry("tc01_foo", "2026-06-12 10:20:41", "PASS")]
    html = render_html(group_by_suite_then_date(entries))
    assert 'class="delete-btn"' in html
    assert "deleteRun(event, 'tc01_foo_20260612_102041')" in html


def test_render_html_delete_button_uses_folder_name():
    entries = [_entry("tc02_bar", "2026-06-12 11:00:00", "FAIL")]
    html = render_html(group_by_suite_then_date(entries))
    folder = "tc02_bar_20260612_110000"
    assert f"deleteRun(event, '{folder}')" in html


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


def test_render_html_groups_by_suite():
    entries = [
        _entry_s("tc01_a", "2026-06-12 10:00:00", "PASS", "HeartSystem"),
        _entry_s("tc01_x", "2026-06-12 10:00:00", "FAIL", "DailyMission"),
    ]
    html = render_html(group_by_suite_then_date(entries))
    assert ">HeartSystem<" in html
    assert ">DailyMission<" in html


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


def test_scan_catalog_air_as_directories(tmp_path):
    from aggregate_report import scan_catalog
    suite = tmp_path / "HeartSystem"
    suite.mkdir()
    air = suite / "tc01_a.air"   # .air is a DIRECTORY (real repo layout)
    air.mkdir()
    (air / "tc01_a.py").write_text("def main(): pass\n", encoding="utf-8")
    assert scan_catalog(tmp_path) == {"HeartSystem": ["tc01_a"]}


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
