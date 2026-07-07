from pixon.common import config
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
    set_time_relative,
    set_level_result,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()


def main():
    # TC02 -- TODO: Add description

    try:
        log_info("Start: tc02_tutorial_fresh_install")
        run_step("tc02 advance to next day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)

        run_step(
            "cold start with parameters",
            cold_start_with_combined,
            heart=5, level=11, coin=1000, fakeads=True, playspeed=6,
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

        run_step("enter level by clicking play", home_page.click_play)
        sleep(2)
        run_step("win level", set_level_result, True)
        sleep(2)
        run_step("Return home", home_page.click_btn_next)
        sleep(2)
        run_step("Close all popup", close_all_popups, home_page)

        log_info("Start: Check verify daily mission icon not visible after unlock")
        if not (daily.wait_for_element(
            daily.btn_daily_mission, timeout=10
        ) or daily.is_notify_visible(
            timeout=5
        )):
            raise AssertionError("Result: Expected: notify visible after unlock | Actual: notify not visible after unlock")
        else:
            log_info("Result: Expected: notify visible after unlock | Actual: notify visible after unlock")
        log_info("End: Check verify daily mission icon not visible after unlock")

        log_info("Start: Check open daily mission popup")
        if not daily.open_daily_mission_popup():
            raise AssertionError("Result: Expected: Daily Mission popup opens | Actual: cannot open Daily Mission popup")
        else:
            log_info("Result: Expected: Daily Mission popup opens | Actual: Daily Mission popup opened")
        log_info("End: Check open daily mission popup")

        log_info("tc02 complete tutorial from popup")
        daily.complete_tutorial_from_popup()

        log_info("Start: Check verify daily mission icon on home")
        if not daily.verify_daily_mission_icon_on_home(timeout=10):
            raise AssertionError("Result: Expected: Daily Mission icon visible | Actual: Daily Mission icon not visible after tutorial")
        else:
            log_info("Result: Expected: Daily Mission icon visible | Actual: Daily Mission icon visible after tutorial")
        log_info("End: Check verify daily mission icon on home")

        log_info("Start: Check verify notify still visible after tutorial")
        if not daily.is_notify_visible(timeout=2):
            raise AssertionError("Result: Expected: notify visible after tutorial | Actual: notify not visible after tutorial")
        else:
            log_info("Result: Expected: notify visible after tutorial | Actual: notify visible after tutorial")
        log_info("End: Check verify notify still visible after tutorial")

        sleep(10)
        log_info("End: tc02_tutorial_fresh_install")
    except Exception as e:
        wrapper.log_error(f"TC02_error: {str(e)}")
        snapshot(filename="tc02_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
