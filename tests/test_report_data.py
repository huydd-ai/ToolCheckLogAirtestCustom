import tempfile
import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from dagster.reports.report_data import RunEntry, compute_metrics, extract_error_from_airtest_log

def test_compute_metrics():
    now = datetime.now()
    runs = [
        RunEntry("test1", now, "PASS", "test1_1", "href1"),
        RunEntry("test2", now, "FAIL", "test2_1", "href2"),
        RunEntry("test3", now, "SKIP", "test3_1", "href3"),
        RunEntry("test4", now, "UNKNOWN", "test4_1", "href4"),
    ]
    
    # 1 PASS, 1 FAIL out of 4 total -> 25% pass rate (since it's pass / total)
    metrics = compute_metrics(runs)
    assert metrics["total"] == 4
    assert metrics["pass"] == 1
    assert metrics["fail"] == 1
    assert metrics["skip"] == 1
    assert metrics["unknown"] == 1
    assert metrics["pass_rate"] == 25
    
    # Trend
    assert len(metrics["trend"]) == 1
    assert metrics["trend"][0]["total"] == 4
    assert metrics["trend"][0]["pass_rate"] == 25
    
def test_flaky_detection():
    now = datetime.now()
    runs = []
    # test_flaky: 1 pass, 1 fail in last 10
    runs.append(RunEntry("test_flaky", now - timedelta(days=1), "PASS", "f1", "h"))
    runs.append(RunEntry("test_flaky", now, "FAIL", "f2", "h"))
    
    # test_stable_pass: only passes
    runs.append(RunEntry("test_stable_pass", now, "PASS", "f3", "h"))
    runs.append(RunEntry("test_stable_pass", now - timedelta(days=1), "PASS", "f4", "h"))
    
    # test_stable_fail: only fails
    runs.append(RunEntry("test_stable_fail", now, "FAIL", "f5", "h"))
    
    metrics = compute_metrics(runs)
    assert metrics["flaky"] == 1

def test_extract_error_from_airtest_log():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as f:
        f.write(b"INFO this is info\nDEBUG this is debug\nTraceback (most recent call last):\n  File 'test.py', line 1\nAssertionError: failed!\n")
        name = f.name
    try:
        err = extract_error_from_airtest_log(Path(name))
        assert err == "AssertionError: failed!"
    finally:
        os.unlink(name)

if __name__ == "__main__":
    pytest.main([__file__])
