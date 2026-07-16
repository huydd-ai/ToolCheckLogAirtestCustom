from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.pages.lucky_spin import LuckySpinPage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
lucky = LuckySpinPage()
heart_page = HeartSystemPage()


def main():
    # TC20 -- TODO: Add description
    # Test Flow:
    # Step 1: Check Failed to tap watch RV on attempt {i+1}
    # Step 2: Check EXP increased
    #

    try:
        log_info("Start: tc20_exp_bar_update")
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
        run_step("close popup before time change", close_all_popups, home_page)
        run_step("tc20 advance to next day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)
        run_step("tc20 reopen daily mission popup", daily.open_daily_mission_popup)
        exp_before = daily.get_exp_progress()
        for i in range(10):
            if not daily.wait_for_element(daily.icon_ads_watch, timeout=2):
                daily.open_daily_mission_popup()
                sleep(1.5)
                if not daily.wait_for_element(daily.icon_ads_watch, timeout=2):
                    log_info(f"Ad icon disappeared on attempt {i+1}, likely reached ad cap. Breaking loop.")
                    break
            
            log_info(f"Start: Check Failed to tap watch RV on attempt {i+1}")
            if not daily.tap(daily.icon_ads_watch):
                raise AssertionError(f"Failed to tap watch RV on attempt {i+1}")
            sleep(10)

        exp_after = daily.get_exp_progress()
        log_info("Start: Check EXP increased")
        if exp_after <= exp_before:
            raise AssertionError(f"Result: Expected: EXP increased | Actual: EXP did not increase: {exp_before} -> {exp_after}")
        else:
            log_info(f"Result: Expected: EXP increased | Actual: EXP increased: {exp_before} -> {exp_after}")
        log_info("End: EXP increased")
        sleep(10)
        log_info("End: tc20_exp_bar_update")
    except Exception as e:
        wrapper.log_error(f"TC20_error: {str(e)}")
        snapshot(filename="tc20_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
