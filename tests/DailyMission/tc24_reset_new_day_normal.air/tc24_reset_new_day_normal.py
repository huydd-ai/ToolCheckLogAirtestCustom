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
from pixon.common import config


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()


def main():
    # TC24 -- TODO: Add description

    try:
        log_info("Start: tc24_reset_new_day_normal")
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
        
        log_info("Start: Read initial active missions")
        initial_active_ids = daily.get_active_mission_ids()
        log_info(f"Initial active missions: {initial_active_ids}")
        log_info("End: Read initial active missions")
        
        log_info("Start: Teardown app and change day")
        from pixon.common.test_flow import stop_app
        stop_app(config.GAME_PACKAGE)
        sleep(2)
        
        run_step("tc24 change day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)
        
        run_step(
            "cold start with parameters (clear_data=False)",
            cold_start_with_combined,
            heart=5, level=11, coin=1000, fakeads=True, playspeed=6,
            clear_data=False, server_sync=True,
        )
        sleep(15)
        for _ in range(15):
            try:
                if home_page.is_at_home():
                    break
            except Exception:
                pass
            sleep(2)
        run_step("Go back homepage after restart", go_home_clean, home_page)
        run_step("Close all popups after restart", close_all_popups, home_page)

        run_step("tc24 open daily mission popup after new day", daily.open_daily_mission_popup)
        run_step("complete tutorial if present after new day", daily.complete_tutorial_from_popup, close_after=False)

        log_info("Start: Check Data reset after new day")
        new_active_ids = daily.get_active_mission_ids()
        log_info(f"New active missions: {new_active_ids}")

        exp_after = daily.get_exp_progress()
        if exp_after > 0:
            raise AssertionError(f"Result: Expected: EXP reset to 0% after new day | Actual: EXP = {exp_after}% (not reset)")
        log_info(f"Result: Expected: EXP reset to 0% | Actual: EXP = {exp_after}% (reset confirmed)")

        if sorted(initial_active_ids) == sorted(new_active_ids):
            log_info(f"Result: Data reset after new day, missions randomly overlapped: {new_active_ids}")
        else:
            log_info(f"Result: Data reset after new day with new missions {new_active_ids}")
            
        log_info("End: Check Data reset after new day")
        sleep(10)
        log_info("End: tc24_reset_new_day_normal")
    except Exception as e:
        wrapper.log_error(f"TC24_error: {str(e)}")
        snapshot(filename="tc24_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
