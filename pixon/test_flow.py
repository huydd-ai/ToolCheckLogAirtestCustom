import logging
import os
import time
from typing import Any, Callable, Optional

from airtest.core.api import stop_app
from airtest.report.report import simple_report
from pixon.common import config as _config
from pixon.common import wrappers as wrapper
from pixon.common.adb_utils import wait_for_app_ready

_logger = logging.getLogger("pixon")

def log_step(message: str) -> None:
    from airtest.core.cv import try_log_screen
    from airtest.core.helper import logwrap, G

    try:
        if hasattr(try_log_screen, "__wrapped__"):
            try_log_screen.__wrapped__()
        else:
            try_log_screen()
    except Exception:
        pass
    G.LOGGER.log(
        "function",
        {
            "name": message,
            "traceback": None,
            "log": message,
            "snapshot": True,
            "call_args": {},
        },
        depth=1,
    )

def run_step(name: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    start = time.time()
    try:
        result = action(*args, **kwargs)
    except BaseException as e:
        elapsed = time.time() - start
        try:
            log_step(f"{name} FAILED ({elapsed:.2f}s): {type(e).__name__}: {e}")
        except Exception:
            pass
        raise
    elapsed = time.time() - start
    log_step(f"{name} ({elapsed:.2f}s)")
    return result

def ensure_home(
    home: Any,
    retries: int = 3,
    settle_seconds: float = 0.5,
) -> None:
    close_all_popups(home)
    if home.is_at_home():
        close_all_popups(home)
        return

    for attempt in range(retries):
        log_step(f"ensure_home attempt {attempt + 1}/{retries}")
        if home.go_home(force=True):
            time.sleep(settle_seconds)
            close_all_popups(home)
            if home.is_at_home():
                log_step("ensure_home resolved")
                return
        wrapper.log_info(f"ensure_home attempt {attempt + 1} failed, retrying")

    raise AssertionError("Not at home after navigation")

def close_all_popups(home: Any, repeat: int = 6, settle: float = 1.0) -> None:
    """Close stacked/chained popups until the screen is verified clean.

    Popups close with an animation and chained popups surface a beat after the
    one above them, so an instant re-scan can miss them. After each close we
    wait `settle`s; we only stop once the screen scans clean twice in a row,
    then warn if a close button is still present.
    """
    log_step(f"close_all_popups scan start (repeat={repeat})")
    closed = 0
    clean = 0
    for _ in range(repeat):
        if wrapper.partial_search(home.btn_close):
            home.close_popup()
            closed += 1
            clean = 0
            time.sleep(settle)  # let the close animation finish / chained popup surface
        else:
            clean += 1
            if clean >= 2:  # confirmed clean on two consecutive scans -> done
                break
            time.sleep(settle)  # give a late/chained popup time to appear
    from pixon.common.matching import wait_stable
    wait_stable(timeout=2)
    if wrapper.partial_search(home.btn_close):
        log_step("close_all_popups WARNING: close button still present after scan")
    if closed:
        log_step(f"close_all_popups closed {closed} popup(s)")

def go_home_clean(home: Any, retries: int = 3) -> None:
    try:
        run_step("ensure app is at home", ensure_home, home, retries, 0.5)
        time.sleep(3)
        return
    except (AssertionError, wrapper.StepError) as e:
        has_close = bool(wrapper.partial_search(home.btn_close))
        has_setting = bool(wrapper.partial_search(home.btn_setting))
        has_home = bool(wrapper.partial_search(home.btn_home))
        has_main_home = bool(wrapper.partial_search(home.btn_main_home))
        has_main_play = bool(wrapper.partial_search(home.btn_main_play))
        raise AssertionError(
            f"(close={has_close}, setting={has_setting}, home={has_home}, "
            f"main_home={has_main_home}, main_play={has_main_play})"
        ) from e

def stop_app_only() -> None:
    """Stop the game app without restoring clock or network.

    Use this for mid-test restarts where you need to change the device clock
    and relaunch with clear_data=False.  Unlike teardown_app() this does NOT
    call restore_system_time() so the accumulated clock offset is preserved.
    """
    try:
        stop_app(_config.GAME_PACKAGE)
        time.sleep(10)
    except Exception as e:
        _logger.warning(f"stop_app_only failed: {e}")

def teardown_app(test_file: Optional[str] = None) -> None:
    try:
        stop_app(_config.GAME_PACKAGE)
        time.sleep(10)
    except Exception as e:
        _logger.warning(f"teardown stop_app failed: {e}")
    # Unblock WAN (network_disconnect leaves an iptables drop chain); no-op if
    # never mutated.
    try:
        from pixon.common.adb_utils import network_reconnect
        network_reconnect()
    except Exception as e:
        _logger.warning(f"teardown network restore failed: {e}")
    # Restore device clock to real time so the next test starts from a clean
    # baseline. Without this, sequential tests accumulate clock drift (each
    # test's +25 h advance stacks) and 24 h-limited events like Lava Quest
    # expire before the next test can interact with them.
    try:
        from pixon.common.adb_utils import restore_system_time
        restore_system_time()
    except Exception as e:
        _logger.warning(f"teardown clock restore failed: {e}")
    try:
        if test_file is None:
            import inspect

            for frame_info in inspect.stack():
                frame_globals = frame_info.frame.f_globals
                if (
                    frame_globals.get("__name__") == "__main__"
                    and "__file__" in frame_globals
                ):
                    test_file = frame_globals["__file__"]
                    break
        if test_file:
            from airtest.core.settings import Settings as ST

            logpath = ST.LOG_DIR if ST.LOG_DIR else True
            output = "report.html"
            logfile = "log.txt"
            if isinstance(logpath, str):
                output = os.path.join(logpath, "report.html")
                if os.path.exists(os.path.join(logpath, "airtest.log")):
                    logfile = "airtest.log"
                elif not os.path.exists(os.path.join(logpath, "log.txt")):
                    _logger.info("Skipping report generation: no logfile found.")
                    return
            simple_report(test_file, logpath=logpath, logfile=logfile, output=output)
    except Exception as e:
        _logger.warning(f"teardown report generation failed: {e}")
    time.sleep(5)

def trigger_daily_reset() -> None:
    """Backgrounds the app, advances time by 24h, and cold starts it to register the new day."""
    from airtest.core.api import keyevent
    from pixon.common.adb_utils import set_time_relative, cold_start_with_combined

    log_step("Backgrounding app to Home screen")
    keyevent("HOME")
    time.sleep(2)

    log_step("Advancing clock by 24 hours")
    set_time_relative(24)
    time.sleep(2)

    log_step("Foregrounding app with profile cold start")
    cold_start_with_combined(
        fakeads=True,
        playspeed=6,
        clear_data=False,
        server_sync=False,
    )

    wait_for_app_ready()
