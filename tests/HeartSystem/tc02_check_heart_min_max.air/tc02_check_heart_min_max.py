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
from pixon.common.adb_utils import cold_start_with_combined, set_param
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 2 — Check heart min (0) and max (5)
    try:
        log_info("Start: setup heart test (heart=5, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 5,
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

        log_info("Start: check max hearts = 5")
        run_step("navigate to home", go_home_clean, home_page)
        count = heart_page.get_heart_count_via_ocr()
        if count != 5:
            raise AssertionError(f"Expected max hearts=5, got {count}")
        else:
            log_info(f"Result: Expected count=5 | Actual count={count}")
        log_info("End: check max hearts = 5")

        log_info("Start: check min hearts = 0")
        set_param("heart", 0)
        sleep(2)
        run_step("navigate to home", go_home_clean, home_page)
        count = heart_page.get_heart_count_via_ocr()
        if count != 0:
            raise AssertionError(f"Expected min hearts=0, got {count}")
        else:
            log_info(f"Result: Expected count=0 | Actual count={count}")
        log_info("End: check min hearts = 0")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC02_error: {str(e)}")
        snapshot(filename="tc02_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
