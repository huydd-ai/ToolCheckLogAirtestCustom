"""Launch/close the LDPlayer emulator for dashboard-triggered test runs.

Single instance, index 0. Windows-only (ldconsole.exe). Consumed by report_server's
/emulator/start and /emulator/stop routes. NOT wired into CLI dagster_run.py.
"""
from __future__ import annotations

import logging
import subprocess
import time

LDCONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"
INDEX = 0
POLL_INTERVAL = 2   # seconds between health polls
STABILIZE = 10      # seconds to let a freshly-booted emulator settle before use

_logger = logging.getLogger("dagster")


def launch() -> None:
    """Start the LDPlayer instance. Raises FileNotFoundError if ldconsole is missing."""
    subprocess.run([LDCONSOLE, "launch", "--index", str(INDEX)], check=False)


def quit() -> None:
    """Close the LDPlayer instance. Best-effort: logs failures, never raises."""
    try:
        subprocess.run([LDCONSOLE, "quit", "--index", str(INDEX)], check=False)
    except Exception as e:  # ldconsole missing/unusable — log, don't surface to UI (ponytail)
        _logger.warning("ldplayer quit failed: %s", e)


def wait_ready(timeout: int = 60, _poll=None, _sleep=time.sleep, _clock=time.monotonic) -> bool:
    """Poll for a booted, ADB-healthy device; on first sighting, sleep STABILIZE then return True.
    Returns False if none appears within `timeout`. The `_`-prefixed args are test seams."""
    if _poll is None:
        from dagster.device.device_manager import device_manager
        _poll = device_manager.get_healthy_devices
    start = _clock()
    while _clock() - start < timeout:
        if _poll():
            _sleep(STABILIZE)
            return True
        _sleep(POLL_INTERVAL)
    return False


if __name__ == "__main__":
    # ponytail: real emulator boot can't be unit-tested — this is the runnable check.
    logging.basicConfig(level=logging.INFO)
    print("launch...", flush=True)
    launch()
    print("wait_ready...", flush=True)
    ok = wait_ready()
    print(f"ready={ok}", flush=True)
    print("quit...", flush=True)
    quit()
    print("done", flush=True)
