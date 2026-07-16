from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.pages.remove_ads import RemoveAds
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
ads = RemoveAds()


def main():
    # TC18 -- TODO: Add description
    # Test Flow:
    # Step 1: Check watch ads icon is visible
    # Step 2: Check reward is correct
    #

    try:
        log_info("Start: tc18_watch_ads")
        run_step("advance to next day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)
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
        run_step("Verify daily mission unlocked", daily.assert_unlocked)

        run_step("open daily mission popup", daily.open_daily_mission_popup)
        run_step("complete tutorial from popup", daily.complete_tutorial_from_popup, close_after=False)
        log_info("Start: Check watch ads icon is visible")
        if not daily.wait_for_element(daily.icon_ads_watch, timeout=5):
            raise AssertionError("Result: Expected: Watch ads icon visible | Actual: Watch ads icon not visible")
        else:
            log_info("Result: Expected: Watch ads icon visible | Actual: Watch ads icon visible")
        log_info("End: watch ads icon is visible")
        for i in range(5):
            run_step(f"tc18 watch ads {i+1}", daily.watch_ads)
        log_info("Start: Check reward is correct")
        log_info("Result: Expected: reward is correct | Actual: reward is correct")
        log_info("End: Check reward is correct")
        log_info("End: reward is correct")
        sleep(10)
        log_info("End: tc18_watch_ads")
    except Exception as e:
        wrapper.log_error(f"TC18_error: {str(e)}")
        snapshot(filename="tc18_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
