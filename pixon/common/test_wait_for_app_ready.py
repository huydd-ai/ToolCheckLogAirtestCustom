"""Self-check for wait_for_app_ready liveness gate (adb_utils.py).

Verifies: after the post-cold-start dwell, wait_for_app_ready polls
check_device_health + _is_app_running; returns silently when both pass;
raises AdbError (non-offline → runner.py fails fast) naming the failing
probe when the window closes with either false.

Run: python -m pytest pixon/common/test_wait_for_app_ready.py
 or: python pixon/common/test_wait_for_app_ready.py
"""
from contextlib import contextmanager

from pixon.common import adb_utils
from pixon.common.adb_errors import AdbError


@contextmanager
def _patched(device_ok, app_up):
    """Swap the two probes + sleep so the gate runs offline, fast, deterministic."""
    orig = {k: getattr(adb_utils, k) for k in ("check_device_health", "_is_app_running", "sleep")}
    adb_utils.check_device_health = lambda **kw: device_ok
    adb_utils._is_app_running = lambda **kw: app_up
    adb_utils.sleep = lambda *a, **k: None
    try:
        yield
    finally:
        for k, v in orig.items():
            setattr(adb_utils, k, v)


def test_both_ok_returns_none():
    with _patched(device_ok=True, app_up=True):
        assert adb_utils.wait_for_app_ready(timeout=0.05) is None


def test_app_dead_raises():
    with _patched(device_ok=True, app_up=False):
        try:
            adb_utils.wait_for_app_ready(timeout=0.05)
            assert False, "expected AdbError"
        except AdbError as e:
            assert "process not running" in str(e)


def test_device_offline_raises():
    with _patched(device_ok=False, app_up=True):
        try:
            adb_utils.wait_for_app_ready(timeout=0.05)
            assert False, "expected AdbError"
        except AdbError as e:
            assert "offline" in str(e)


if __name__ == "__main__":
    test_both_ok_returns_none()
    test_app_dead_raises()
    test_device_offline_raises()
    print("all wait_for_app_ready self-checks passed")
