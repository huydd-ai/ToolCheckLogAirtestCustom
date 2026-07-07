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
    # TC08 -- TODO: Add description

    try:
        log_info("Start: tc08_visual_progress")
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
        
        claimable_ids = daily.get_claimable_mission_ids()
        mission_id = None
        
        if claimable_ids:
            mission_id = claimable_ids[0]
        else:
            active_ids = daily.get_active_mission_ids()
            if not active_ids:
                raise AssertionError("No active or claimable missions found after tutorial!")
            mission_id = daily.get_easiest_mission_id(active_ids)
            
        log_info(f"Start: tc08 Check visual progress on {mission_id}")
        db = daily._load_mission_db()
        mission_data = next((m for m in db if m["id"] == mission_id), None)
        mission_name = mission_data["ocr_text"] if mission_data else mission_id
            
        if not claimable_ids:
            log_info(f"Start: play mission until completable [{mission_name}]")
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts and not daily.is_mission_completable(mission_id):
                run_step(f"Play mission: [{mission_name}] (Attempt {attempt + 1})", daily.execute_mission_logic, mission_id, game, home_page)
                run_step("Reopen daily mission popup", daily.open_daily_mission_popup)
                attempt += 1
                
            if not daily.is_mission_completable(mission_id):
                raise AssertionError(f"Mission '{mission_name}' did not complete after {max_attempts} attempts.")
            log_info(f"End: play mission until completable [{mission_name}]")

        # verify_mission_and_claim automatically asserts that global EXP increased visually
        success = run_step(f"Verify visual progress and claim: [{mission_name}]", daily.verify_mission_and_claim, mission_id)
        if not success:
            raise AssertionError(f"Failed to verify visual progress update for mission: {mission_name}")
            
        run_step("close popup", close_all_popups, home_page)
        
        log_info(f"Start: Check Visual progress updated for [{mission_name}]")
        log_info(f"Result: Expected: Visual progress updated | Actual: Visual progress updated for [{mission_name}]")
        log_info(f"End: Check Visual progress updated for [{mission_name}]")
        log_info(f"End: Visual progress updated for [{mission_name}]")
        sleep(10)
        log_info("End: tc08_visual_progress")
    except Exception as e:
        wrapper.log_error(f"TC08_error: {str(e)}")
        snapshot(filename="tc08_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
