from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()


def main():
    # TC03 -- TODO: Add description
    # Test Flow:
    # Step 1: Check verify daily mission icon not visible after unlock
    # Step 2: Check open daily mission popup
    # Step 3: Check verify daily mission icon on home
    #

    try:
        log_info("Start: tc03_tutorial_reinstall")
        run_step("advance to next day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)
        run_step(
            "cold start with parameters",
            cold_start_with_combined,
            heart=5, level=11, coin=1000, fakeads=True, playspeed=6,
            clear_data=False, server_sync=False,
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
        run_step("Verify daily mission unlocked", daily.assert_unlocked)

        log_info("Start: Check verify daily mission icon not visible after unlock")
        if not daily.is_notify_visible():
            raise AssertionError("Result: Expected: notify visible on Daily Mission icon | Actual: notify not visible on Daily Mission icon")
        else:
            log_info("Result: Expected: notify visible on Daily Mission icon | Actual: notify visible on Daily Mission icon")
        log_info("End: Check verify daily mission icon not visible after unlock")

        log_info("Start: Check open daily mission popup")
        if not daily.open_daily_mission_popup():
            raise AssertionError("Result: Expected: open Daily Mission popup | Actual: cannot open Daily Mission popup")
        else:
            log_info("Result: Expected: open Daily Mission popup | Actual: open Daily Mission popup")
        log_info("End: Check open daily mission popup")

        log_info("tc03 complete tutorial from popup")
        run_step("tc03 complete tutorial from popup", daily.complete_tutorial_from_popup, force_trigger=True)

        log_info("Start: Check verify daily mission icon on home")
        if not daily.verify_daily_mission_icon_on_home(timeout=25):
            raise AssertionError("Result: Expected: Daily Mission icon visible | Actual: Daily Mission icon not visible after tutorial")
        else:
            log_info("Result: Expected: Daily Mission icon visible | Actual: Daily Mission icon visible after tutorial")
        log_info("End: Check verify daily mission icon on home")
        sleep(10)
        log_info("End: tc03_tutorial_reinstall")
    except Exception as e:
        wrapper.log_error(f"TC03_error: {str(e)}")
        snapshot(filename="tc03_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
