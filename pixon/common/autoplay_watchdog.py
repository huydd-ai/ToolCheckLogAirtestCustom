
import time
from airtest.core.api import sleep
from pixon.common import wrappers as wrapper
from pixon.common import config as _config
from pixon.common.adb_utils import (
    cold_start_with_combined,
    is_app_running,
    set_autoplay,
    warm_send_json,
)
from pixon.pages.game_page import GamePage

STUCK_THRESHOLD_SECONDS = 60.0
RECOVERY_LOAD_WAIT_SECONDS = _config.RECOVERY_LOAD_WAIT_SEC   # env/config.json-tunable
MAX_RECOVERIES = 3
POLL_INTERVAL_SECONDS = 2.0
RECOVERY_COLD_PLAYSPEED = _config.RECOVERY_COLD_PLAYSPEED     # env/config.json-tunable
APP_UP_POLL_TIMEOUT = 45.0

def _recover(resume_level, **autoplay_kwargs):
    cold_start_with_combined(
        fakeads=True,
        playspeed=RECOVERY_COLD_PLAYSPEED,
        level=resume_level,
        clear_data=False,
        server_sync=True,
    )
    sleep(RECOVERY_LOAD_WAIT_SECONDS)

    deadline = time.time() + APP_UP_POLL_TIMEOUT
    up = is_app_running()
    while not up and time.time() < deadline:
        sleep(1)
        up = is_app_running()
    if not up:
        raise AssertionError(
            "watchdog: app did not come up after recovery cold start"
        )
        
    ok = set_autoplay(True, **autoplay_kwargs)
    if not ok:
        wrapper.log_info("watchdog: warm set_autoplay did not land after recovery")
    return ok

def autoplay_with_watchdog(
    game: GamePage,
    target_level: int,
    *,
    autoplay_in_watchdog: bool = True,
    stuck_threshold: float = STUCK_THRESHOLD_SECONDS,
    max_recoveries: int = MAX_RECOVERIES,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    **autoplay_kwargs
) -> int:
    # Graceful backward compatibility for 15 existing test suites
    if "coin" not in autoplay_kwargs:
        autoplay_kwargs["coin"] = 5000

    if autoplay_in_watchdog:
        set_autoplay(True, **autoplay_kwargs)
        
    last_level = None
    last_change_ts = time.time()
    consecutive_recoveries = 0
    while True:
        try:
            current_lv = game.get_current_level()
        except RuntimeError as exc:
            wrapper.log_warning(f"watchdog: get_current_level raised ({exc})")
            current_lv = None

        now = time.time()
        if current_lv is not None and current_lv != last_level:

            last_level = current_lv
            last_change_ts = now
            consecutive_recoveries = 0

        if current_lv is not None and current_lv >= target_level:
            if autoplay_in_watchdog:
                set_autoplay(False, heart=5)
            return current_lv

        if now - last_change_ts >= stuck_threshold:
            if consecutive_recoveries >= max_recoveries:
                raise AssertionError(
                    f"autoplay stuck at level {last_level} after "
                    f"{max_recoveries} consecutive recoveries"
                )
            consecutive_recoveries += 1
            wrapper.log_info(
                f"watchdog: level frozen at {last_level} for "
                f">={stuck_threshold}s; recovery #{consecutive_recoveries}"
            )
            _recover(last_level, **autoplay_kwargs)
            last_change_ts = time.time()

        sleep(poll_interval)
