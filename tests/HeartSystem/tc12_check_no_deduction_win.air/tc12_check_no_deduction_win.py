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
    # STT 23 — Case 1 (no deduction): Win level → no heart deducted
    try:
        log_info("Start: setup (heart=5, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 5,
            "level": 12,
            "coin": 5000,
            "booster": {"drill": 20, "hammer": 20, "magnet": 20},
            "playspeed": config.GAME_START_PLAY_SPEED,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup")

        log_info("Start: read heart count before game")
        count_before = heart_page.get_heart_count_via_ocr()
        log_info(f"Heart count before: {count_before}")
        log_info("End: read heart count before game")

        log_info("Start: enter game and trigger win")
        run_step("click play", home_page.click_play)
        sleep(5)
        run_step("set level win", set_param, "set_level_win", True)
        sleep(3)
        run_step("tap next", home_page.tap, home_page.btn_next)
        sleep(2)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: enter game and trigger win")

        log_info("Start: verify no heart deduction on win")
        count_after = heart_page.get_heart_count_via_ocr()
        log_info(f"Heart count after: {count_after}")
        if count_after != count_before:
            raise AssertionError(
                f"Heart deducted on win: before={count_before}, after={count_after}"
            )
        else:
            log_info(f"Result: Expected count_after={count_before} | Actual count_after={count_after}")
        log_info("End: verify no heart deduction on win")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC12_error: {str(e)}")
        snapshot(filename="tc12_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
