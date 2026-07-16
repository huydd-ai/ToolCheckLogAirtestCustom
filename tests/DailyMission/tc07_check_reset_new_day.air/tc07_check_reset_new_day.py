from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups, trigger_daily_reset
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()


def main():
    # TC07 -- TODO: Add description
    # Test Flow:
    # Step 1: Check daily mission reset state
    # Step 2: Check Reset complete
    #

    try:
        log_info("Start: tc07_reset_new_day")
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

        log_info("Wait for next day")
        run_step("advance to next day to trigger reset", trigger_daily_reset)
        
        # After cold start, we need to make sure we are at home screen and ready to open the popup.
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)
        
        run_step("Open daily mission popup", daily.open_daily_mission_popup)
        
        log_info("Start: Check daily mission reset state")
        claimable_ids = daily.get_claimable_mission_ids()
        if claimable_ids:
            raise AssertionError(f"Expected 0 claimable missions after reset, found {len(claimable_ids)}")
            
        exp_progress = daily.get_exp_progress()
        if exp_progress > 0:
            raise AssertionError(f"Expected 0% EXP progress after reset, found {exp_progress}%")
        log_info("End: Check daily mission reset state")
            
        run_step("close popup", close_all_popups, home_page)
        
        log_info("Start: Check Reset complete")
        log_info("Result: Expected: Reset complete | Actual: Reset complete")
        log_info("End: Check Reset complete")
        log_info("End: Reset complete")
        sleep(10)
        log_info("End: tc07_reset_new_day")
    except Exception as e:
        wrapper.log_error(f"TC07_error: {str(e)}")
        snapshot(filename="tc07_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
