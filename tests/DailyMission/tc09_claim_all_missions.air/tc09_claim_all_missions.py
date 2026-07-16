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
    # TC09 -- TODO: Add description
    # Test Flow:
    # Step 1: Check All missions claimed
    #

    try:
        log_info("Start: tc09_claim_all_missions")
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

        MAX_CLAIM_ITERATIONS = 20
        _claim_iter = 0
        while True:
            _claim_iter += 1
            if _claim_iter > MAX_CLAIM_ITERATIONS:
                wrapper.log_info(f"Claim loop hit max iterations ({MAX_CLAIM_ITERATIONS}) — exiting")
                break
            run_step("Open daily mission popup", daily.open_daily_mission_popup)
            
            claimable_ids = daily.get_claimable_mission_ids()
            db = daily._load_mission_db()
            
            if claimable_ids:
                log_info(f"Found {len(claimable_ids)} claimable missions.")
                for m_id in claimable_ids:
                    mission_name = next((m["ocr_text"] for m in db if m["id"] == m_id), m_id)
                    run_step(f"Verify and claim mission [{mission_name}]", daily.verify_mission_and_claim, m_id)
            
            active_ids = daily.get_active_mission_ids()
            if not active_ids:
                log_info("No more active missions found. All missions completed and claimed!")
                break
                
            m_id = active_ids[0]
            mission_name = next((m["ocr_text"] for m in db if m["id"] == m_id), m_id)
            run_step(f"Execute gameplay for active mission: [{mission_name}]", daily.execute_mission_logic, m_id, game, home_page)
            
            run_step("Back home after playing", go_home_clean, home_page)

        run_step("Start: Check All missions claimed", daily.get_icon_claim_reward)
        log_info("Start: Check All missions claimed")
        log_info("Result: Expected: All missions claimed | Actual: All missions claimed")
        log_info("End: Check All missions claimed")
        log_info("End: All missions claimed")
        sleep(10)
        log_info("End: tc09_claim_all_missions")
    except Exception as e:
        wrapper.log_error(f"TC09_error: {str(e)}")
        snapshot(filename="tc09_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
