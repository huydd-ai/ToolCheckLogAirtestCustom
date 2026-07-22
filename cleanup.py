"""
Report cleanup utilities for dagster.
Handles deletion of report folders and their contents (log files, screenshots, videos, etc).
"""

import shutil
from pathlib import Path


def delete_report_folder(report_path: Path) -> bool:
    """
    Delete entire report folder and all contents.

    Args:
        report_path: Path to report folder (e.g., report_run/<stem>_<timestamp>/)

    Returns:
        True if deletion succeeded, False otherwise
    """
    if not report_path.exists():
        return False

    if not report_path.is_dir():
        return False

    try:
        shutil.rmtree(report_path)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete {report_path}: {e}")
        return False


def delete_reports_by_pattern(report_root: Path, pattern: str) -> int:
    """
    Delete report folders matching a pattern.

    Args:
        report_root: Base report directory (report_run/)
        pattern: Glob pattern (e.g., "*_20260630_*" or "test_name_*")

    Returns:
        Number of folders deleted
    """
    if not report_root.exists():
        return 0

    deleted = 0
    for report_dir in sorted(report_root.glob(pattern)):
        if report_dir.is_dir():
            if delete_report_folder(report_dir):
                print(f"[INFO] Deleted: {report_dir.name}")
                deleted += 1
            else:
                print(f"[WARN] Failed to delete: {report_dir.name}")

    return deleted


def delete_reports_older_than(report_root: Path, days: int) -> int:
    """
    Delete report folders older than specified days.

    Args:
        report_root: Base report directory (report_run/)
        days: Number of days; folders older than this are deleted

    Returns:
        Number of folders deleted
    """
    import time

    if not report_root.exists():
        return 0

    current_time = time.time()
    cutoff_time = current_time - (days * 86400)  # 86400 seconds per day
    deleted = 0

    for report_dir in sorted(report_root.glob("*")):
        if not report_dir.is_dir():
            continue

        if report_dir.stat().st_mtime < cutoff_time:
            if delete_report_folder(report_dir):
                print(f"[INFO] Deleted (old): {report_dir.name}")
                deleted += 1
            else:
                print(f"[WARN] Failed to delete: {report_dir.name}")

    return deleted
