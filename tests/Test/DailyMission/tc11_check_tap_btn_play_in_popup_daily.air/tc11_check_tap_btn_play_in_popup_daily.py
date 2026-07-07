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
    # TC11 -- TODO: Add description

    try:
        log_info("Start: tc11_play_popup")
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
        log_info("Start: Check Play button found in popup")
        active_ids = daily.get_active_mission_ids()
        db = daily._load_mission_db()
        
        # Exclude SPIN missions
        non_spin_ids = [m["id"] for m in db if m["id"] in active_ids and "SPIN" not in m.get("task_type", "")]
        
        if not non_spin_ids:
            raise AssertionError("Result: Expected: non-spin mission | Actual: All missions are spin, cannot proceed")
        
        target_id = daily.get_easiest_mission_id(non_spin_ids)
        target_mission = next(m for m in db if m["id"] == target_id)
        mission_name = target_mission["ocr_text"]
        
        screen = wrapper.get_screen()
        row = daily._find_mission_row(screen, mission_name, [daily.btn_play_daily])
        
        if row is None:
            raise AssertionError(f"Result: Expected: Play button in popup | Actual: Play button not found for {mission_name}")
        else:
            log_info(f"Result: Expected: Play button in popup | Actual: Play button found for {mission_name}")
            
        log_info("End: Check Play button found in popup")
        run_step("Tap Play button", daily.tap, row["pos"])
        log_info("Start: Check In game after tapping Play")
        if not game.wait_for_element(game.booster[0], timeout=20):
            raise AssertionError("Result: Expected: In game | Actual: Not in game after tapping Play")
        else:
            log_info("Result: Expected: In game | Actual: In game")
        log_info("End: Check In game after tapping Play")
        sleep(10)
        log_info("End: tc11_play_popup")
    except Exception as e:
        wrapper.log_error(f"TC11_error: {str(e)}")
        snapshot(filename="tc11_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
