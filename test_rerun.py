"""Tests for async rerun pipeline."""
from pathlib import Path
from reporting import write_log_txt


def test_write_log_txt_prepends_air_path(tmp_path):
    air_path = tmp_path / "tc01_login.air"
    write_log_txt(tmp_path, "tc01_login", [], None, air_path=air_path)
    first_line = (tmp_path / "log.txt").read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"AIR_PATH={air_path.resolve()}"


def test_write_log_txt_no_air_path_unchanged(tmp_path):
    write_log_txt(tmp_path, "tc01_login", [], None)
    first_line = (tmp_path / "log.txt").read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("# tc01_login")


# ── helpers in report_server ──────────────────────────────────────────────────

def test_extract_air_path_found(tmp_path):
    from report_server import extract_air_path
    log = tmp_path / "log.txt"
    log.write_text("AIR_PATH=/path/to/tc01.air\n# tc01\n", encoding="utf-8")
    assert extract_air_path(log) == "/path/to/tc01.air"


def test_extract_air_path_missing_header(tmp_path):
    from report_server import extract_air_path
    log = tmp_path / "log.txt"
    log.write_text("# tc01\n# Status: PASS\n", encoding="utf-8")
    assert extract_air_path(log) is None


def test_extract_air_path_no_file(tmp_path):
    from report_server import extract_air_path
    assert extract_air_path(tmp_path / "missing.txt") is None


def test_find_newest_folder(tmp_path):
    from report_server import _find_newest_folder
    (tmp_path / "tc01_login_20260619_100000").mkdir()
    (tmp_path / "tc01_login_20260619_110000").mkdir()
    (tmp_path / "tc02_other_20260619_100000").mkdir()
    result = _find_newest_folder(tmp_path, "tc01_login")
    assert result == "tc01_login_20260619_110000"


def test_find_newest_folder_none(tmp_path):
    from report_server import _find_newest_folder
    assert _find_newest_folder(tmp_path, "tc01_login") is None


def test_compute_etag_stable():
    from report_server import _compute_etag
    a = _compute_etag(["tc01_20260619_100000", "tc02_20260619_110000"])
    b = _compute_etag(["tc02_20260619_110000", "tc01_20260619_100000"])
    assert a == b  # order-independent
    assert len(a) == 16
