from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.common.test_flow import (
    run_step,
    teardown_app,
    stop_app_only,
    go_home_clean,
    close_all_popups,
)
from pixon.common.adb_utils import cold_start_with_combined, cold_start_with_json
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 31 — Heart data persists across app restart (Heart = 3/5)
    try:
        log_info("Start: setup heart test (heart=3, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 3,
            "level": 12,
            "coin": 5000,
            "playspeed": config.GAME_START_PLAY_SPEED,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        log_info("Start: verify initial heart count")
        count_v1 = heart_page.get_heart_count_via_ocr()
        if count_v1 != 3:
            raise AssertionError(f"Expected heart=3, got {count_v1}")
        else:
            log_info(f"Result: Expected count=3 | Actual count={count_v1}")
        log_info("End: verify initial heart count")

        log_info("Start: stop and restart app to simulate overwrite persistence")
        # stop only — mid-test teardown_app restores clock/network and emits a report
        run_step("stop app", stop_app_only)
        run_step("cold start app", cold_start_with_json, {"fakeads": True, "playspeed": 6, "clear_data": True, "server_sync": False})
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: stop and restart app")

        log_info("Start: verify heart persisted after restart")
        count_v2 = heart_page.get_heart_count_via_ocr()
        if count_v2 != 3:
            raise AssertionError(
                f"Heart data not persisted after restart: expected 3, got {count_v2}"
            )
        else:
            log_info(f"Result: Expected count=3 | Actual count={count_v2}")
        log_info("End: verify heart persisted after restart")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC18_error: {str(e)}")
        snapshot(filename="tc18_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
