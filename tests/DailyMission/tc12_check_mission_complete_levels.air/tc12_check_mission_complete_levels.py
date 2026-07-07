from pixon.common import config
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


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
lucky_spin = LuckySpinPage()


def main():
    # TC12 -- TODO: Add description

    try:
        log_info("Start: tc12_complete_levels")
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

        # The complete_tutorial_from_popup already clicks tap_to_continue if present.
        target_task_type = "COMPLETE_LEVEL"
        MAX_REROLLS = 25
        log_info(f"Start: find or reroll mission {target_task_type}")
        mission_data, _ = daily.find_or_reroll_mission(target_task_type, home_page=home_page, max_rerolls=MAX_REROLLS)

        if not mission_data:
            raise AssertionError(f"No active mission of type {target_task_type} after {MAX_REROLLS} rerolls!")
        log_info(f"End: find or reroll mission {target_task_type}")
            
        mission_id = mission_data["id"]
        mission_name = mission_data["ocr_text"]
        
        log_info(f"Start: play mission until completable [{mission_name}]")
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts and not daily.is_mission_completable(mission_id):
            run_step(f"Play mission: [{mission_name}] (Attempt {attempt + 1})", daily.execute_mission_logic, mission_id, game, home_page)
            run_step("Reopen daily mission popup", daily.open_daily_mission_popup)
            # Wait for the progress bar animation (PLAY -> COLLECT) to finish so is_mission_completable reads the correct state
            sleep(3)
            attempt += 1
            
        if not daily.is_mission_completable(mission_id):
            raise AssertionError(f"Mission '{mission_name}' did not complete after {max_attempts} attempts.")
        log_info(f"End: play mission until completable [{mission_name}]")

        success = run_step(f"Verify visual progress and claim: [{mission_name}]", daily.verify_mission_and_claim, mission_id)
        if not success:
            raise AssertionError(f"Failed to verify visual progress update for mission: {mission_name}")
            
        run_step("close popup", close_all_popups, home_page)
        
        log_info(f"Start: Check Mission [{mission_name}] marked as complete & Verification")
        log_info(f"Result: Expected: Mission marked as complete | Actual: Mission [{mission_name}] successfully completed and verified")
        log_info(f"End: Check Mission [{mission_name}] marked as complete & Verification")
        sleep(10)
        log_info(f"End: tc12_complete_levels successfully tested [{mission_name}]")
    except Exception as e:
        wrapper.log_error(f"TC12_error: {str(e)}")
        snapshot(filename="tc12_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
