from datetime import datetime
from pathlib import Path

from aggregate_report import parse_run_folder_name, extract_status, RunEntry, scan_runs


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
    log = _write(
        tmp_path,
        "log.txt",
        "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: PASS\n",
    )
    assert extract_status(log) == "PASS"


def test_extract_status_fail(tmp_path):
    log = _write(
        tmp_path,
        "log.txt",
        "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: FAIL\n",
    )
    assert extract_status(log) == "FAIL"


def test_extract_status_skip(tmp_path):
    log = _write(
        tmp_path,
        "log.txt",
        "# tc01\n# Run: 2026-06-12 10:22:15\n# Status: SKIP\n",
    )
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
