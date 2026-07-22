"""Self-check for _send_intent effect-verification + retry gate (adb_utils.py).

Verifies: after `am start`, _send_intent polls _is_app_running; retries the send
up to SEND_INTENT_MAX_ATTEMPTS; raises AdbCommandFailedError (a non-offline
AdbError, so runner.py fails fast) if the app never comes up.

Run: python -m pytest pixon/common/test_send_intent_verify.py
 or: python pixon/common/test_send_intent_verify.py
"""
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator

from pixon.common import adb_utils
from pixon.common.adb_errors import AdbCommandFailedError


@contextmanager
def _patched(app_up_fn: Callable[[Dict[str, int]], bool],
             stdout_fn: Callable[[Dict[str, int]], str] = lambda s: "Starting: Intent { ... }",
             stderr_fn: Callable[[Dict[str, int]], str] = lambda s: "") -> Iterator[Dict[str, int]]:
    """Swap module globals so _send_intent runs offline, fast, and deterministic.

    stdout_fn/stderr_fn(state) -> the am start stdout/stderr to simulate. Real am
    start prints acceptance ("Starting: ...") to stdout and rejection ("Error type
    3 / Error: Activity class ... does not exist") to STDERR, both with exit 0 —
    so the accept check must read both streams.
    """
    state = {"sends": 0}
    orig = {k: getattr(adb_utils, k) for k in
            ("run_adb_command", "_is_app_running", "sleep", "SEND_INTENT_UP_TIMEOUT")}
    orig_warn = adb_utils.wrapper.log_warning

    def fake_run(cmd: Any, **kw: Any) -> adb_utils.AdbResult:
        state["sends"] += 1
        return adb_utils.AdbResult(success=True, stdout=stdout_fn(state), stderr=stderr_fn(state))

    setattr(adb_utils, "run_adb_command", fake_run)
    adb_utils._is_app_running = lambda **kw: app_up_fn(state)
    adb_utils.sleep = lambda *a, **k: None
    adb_utils.SEND_INTENT_UP_TIMEOUT = 0.02
    adb_utils.wrapper.log_warning = lambda *a, **k: None
    try:
        yield state
    finally:
        for k, v in orig.items():
            setattr(adb_utils, k, v)
        adb_utils.wrapper.log_warning = orig_warn


def test_app_up_first_try_sends_once() -> None:
    with _patched(lambda s: True) as state:
        assert adb_utils._send_intent({"x": 1}, serial="dev") is True
        assert state["sends"] == 1


def test_app_never_up_raises_after_max_attempts() -> None:
    with _patched(lambda s: False) as state:
        try:
            adb_utils._send_intent({"x": 1}, serial="dev")
            assert False, "expected AdbCommandFailedError"
        except AdbCommandFailedError:
            pass
        assert state["sends"] == adb_utils.SEND_INTENT_MAX_ATTEMPTS


def test_app_up_on_third_attempt_no_raise() -> None:
    # app reports up only once the 3rd send has fired
    with _patched(lambda s: s["sends"] >= 3) as state:
        assert adb_utils._send_intent({"x": 1}, serial="dev") is True
        assert state["sends"] == 3


def test_am_error_on_stderr_never_accepted_raises() -> None:
    # Real am start: exits 0, "Starting: ..." on stdout, "Error type 3 / Error:
    # Activity class ... does not exist" on STDERR. Intent rejected -> must retry
    # (skipping the app-up poll) and raise after max attempts, even though
    # _is_app_running would return True.
    with _patched(lambda s: True,
                  stdout_fn=lambda s: "Starting: Intent { cmp=pkg/.NoSuchXYZ }",
                  stderr_fn=lambda s: "Error type 3\nError: Activity class {pkg/.NoSuchXYZ} does not exist.") as state:
        try:
            adb_utils._send_intent({"x": 1}, serial="dev")
            assert False, "expected AdbCommandFailedError"
        except AdbCommandFailedError:
            pass
        assert state["sends"] == adb_utils.SEND_INTENT_MAX_ATTEMPTS


def test_warm_delivered_line_accepted() -> None:
    # warm single-top ack ("delivered to currently running top activity") has no
    # "Error" -> accepted; app already up -> pass on first send.
    with _patched(lambda s: True,
                  stdout_fn=lambda s: "Warning: Activity not started, intent has been "
                                      "delivered to currently running top activity.") as state:
        assert adb_utils._send_intent({"x": 1}, warm_start=True, serial="dev") is True
        assert state["sends"] == 1


if __name__ == "__main__":
    test_app_up_first_try_sends_once()
    test_app_never_up_raises_after_max_attempts()
    test_app_up_on_third_attempt_no_raise()
    test_am_error_on_stderr_never_accepted_raises()
    test_warm_delivered_line_accepted()
    print("OK: all _send_intent verify checks passed")
