from datetime import datetime

from aggregate_report import parse_run_folder_name


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
