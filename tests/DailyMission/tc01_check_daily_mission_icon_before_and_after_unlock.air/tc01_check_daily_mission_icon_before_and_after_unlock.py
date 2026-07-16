from pixon.common.test_flow import close_all_popups
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_param,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()


def main():
    # TC01 -- TODO: Add description
    # Test Flow:
    # Step 1: Check Daily Mission icon appeared at level 10!
    # Step 2: Check daily mission icon after level 11
    # Step 3: Check Daily Mission icon appeared at level 11!
    #

    try:
        log_info("Start: tc01_check_daily_mission_icon_before_and_after_unlock")
        run_step(
            "cold start with parameters",
            cold_start_with_combined,
            heart=5, level=10, coin=1000, fakeads=True, playspeed=6,
            clear_data=True, server_sync=False,
        )
        sleep(15)
        for _ in range(15):
            try:
                if home_page.is_at_home():
                    break
            except Exception:
                pass
            sleep(2)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Check Daily Mission icon appeared at level 10!")
        if not daily.wait_for_element(daily.btn_daily_mission, timeout=3):
            raise AssertionError("Result: Expected: daily mission icon does not appear at lv10 | Actual: daily mission icon appears at lv10")
        else:
            log_info("Result: Expected: daily mission icon does not appear at lv10 | Actual: daily mission icon does not appear at lv10")
        log_info("End: Check daily mission icon did not appear at lv10")

        log_info("Start: Check daily mission icon after level 11")
        run_step("enter level by clicking play", home_page.click_play)
        sleep(2)
        run_step("cheat level to 11", set_param, "level", 11)
        sleep(2)
        run_step("win level", set_param, "set_level_win", True)
        sleep(2)
        run_step("tap next to back home", home_page.click_btn_next)
        sleep(1)
        run_step("Close all popups", close_all_popups, home_page)
        sleep(2)

        log_info("Start: Check Daily Mission icon appeared at level 11!")
        if not daily.wait_for_element(daily.btn_daily_mission_notify, timeout=10):
            raise AssertionError("Result: Expected: daily mission icon appear after lv11 | Actual: daily mission icon does not appear after lv11")
        else:
            log_info("Result: Expected: daily mission icon appear after lv11 | Actual: daily mission icon appear after lv11")
        log_info("End: Check daily mission icon appear after lv11")
        sleep(10)
        log_info("End: tc01_check_daily_mission_icon_before_and_after_unlock")
    except Exception as e:
        wrapper.log_error(f"TC01_error: {str(e)}")
        snapshot(filename="tc01_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
