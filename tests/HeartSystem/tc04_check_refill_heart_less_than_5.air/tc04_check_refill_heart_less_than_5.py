from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)
from pixon.common.adb_utils import cold_start_with_combined
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 4 — Case 1: heart < 5 → refill timer visible, min=0 max=5
    try:
        log_info("Start: setup heart test (heart=3, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 3,
            "level": 12,
            "playspeed": config.GAME_START_PLAY_SPEED,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        log_info("Start: verify heart count is 3")
        count = heart_page.get_heart_count_via_ocr()
        if count != 3:
            raise AssertionError(f"Expected heart=3, got {count}")
        else:
            log_info(f"Result: Expected count=3 | Actual count={count}")
        log_info("End: verify heart count is 3")

        log_info("Start: verify refill timer visible")
        timer_visible = heart_page.is_heart_timer_visible(timeout=5)
        if not timer_visible:
            raise AssertionError("Expected refill timer to be visible when heart < 5, got False")
        else:
            log_info(f"Result: Expected timer_visible=True | Actual timer_visible={timer_visible}")
        log_info("End: verify refill timer visible")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC04_error: {str(e)}")
        snapshot(filename="tc04_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
