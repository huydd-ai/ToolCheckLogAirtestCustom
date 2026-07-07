from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.pages.lucky_spin import LuckySpinPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)
from pixon.common import config


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
lucky = LuckySpinPage()


def main():
    # TC23 -- TODO: Add description

    try:
        log_info("Start: tc23_resume_app")
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
        
        run_step("close popup before restart", close_all_popups, home_page)
        
        log_info("Start: Cold start without clearing data (OFFLINE)")
        from pixon.common.test_flow import stop_app
        from pixon.common.adb_utils import network_disconnect
        
        run_step("Disconnect network", network_disconnect)
        sleep(15)
        stop_app(config.GAME_PACKAGE)
        sleep(2)
        
        run_step(
            "cold start with parameters (clear_data=False)",
            cold_start_with_combined,
            heart=5, fakeads=True, playspeed=6,
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
        run_step("Go back homepage after restart", go_home_clean, home_page)
        run_step("Close all popups after restart", close_all_popups, home_page)
        
        run_step("open daily mission popup again", daily.open_daily_mission_popup)
        run_step("complete tutorial from popup", daily.complete_tutorial_from_popup, close_after=False)
        
        log_info("Start: Check missions fit with old data")
        new_active_ids = daily.get_active_mission_ids()
        log_info(f"New active missions: {new_active_ids}")
        
        if sorted(initial_active_ids) != sorted(new_active_ids):
            raise AssertionError(f"Result: Expected: Active missions match {initial_active_ids} | Actual: Missions changed to {new_active_ids}")
        else:
            log_info(f"Result: Expected: Active missions match {initial_active_ids} | Actual: Active missions match {new_active_ids}")
            
        log_info("End: Check missions fit with old data")
        sleep(10)
        log_info("End: tc23_resume_app")
    except Exception as e:
        wrapper.log_error(f"TC23_error: {str(e)}")
        snapshot(filename="tc23_error.png")
    finally:
        try:
            from pixon.common.adb_utils import network_reconnect
            run_step("Reconnect network", network_reconnect)
        except Exception as e:
            wrapper.log_error(f"Failed to reconnect network: {e}")
        teardown_app()


if __name__ == "__main__":
    main()
