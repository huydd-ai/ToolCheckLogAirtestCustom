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
from pixon.common.adb_utils import cold_start_with_combined, set_param, set_time_relative
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 22 — Regen tick during win: heart timer ticks while in-game
    try:
        log_info("Start: setup heart test (heart=4, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 4,
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

        log_info("Start: verify initial heart count")
        count_before = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count before: {count_before}")
        if count_before != 4:
            raise AssertionError(f"Expected 4 hearts, got {count_before}")
        else:
            log_info(f"Result: Expected count=4 | Actual count={count_before}")
        log_info("End: verify initial heart count")

        log_info("Start: enter game")
        run_step("click play", home_page.click_play)
        sleep(5)
        log_info("End: enter game")

        log_info("Start: advance clock 30 min to trigger regen tick")
        run_step("advance clock by 0.5 hours", set_time_relative, 0.5)
        sleep(3)
        log_info("End: advance clock")

        log_info("Start: win level and return home")
        run_step("set param set_level_win True", set_param, "set_level_win", True)
        sleep(3)
        run_step("tap next button", home_page.tap, home_page.btn_next)
        sleep(2)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: win level and return home")

        log_info("Start: verify heart count increased after regen tick")
        count_after = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count after win + regen: {count_after}")
        if count_after <= count_before:
            raise AssertionError(
                f"Regen did not tick during win: before={count_before}, after={count_after}"
            )
        else:
            log_info(f"Result: Expected count_after > {count_before} | Actual count_after={count_after}")
        log_info("End: verify heart count increased after regen tick")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC22_error: {str(e)}")
        snapshot(filename="tc22_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
