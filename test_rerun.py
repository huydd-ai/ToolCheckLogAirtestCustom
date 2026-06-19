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
