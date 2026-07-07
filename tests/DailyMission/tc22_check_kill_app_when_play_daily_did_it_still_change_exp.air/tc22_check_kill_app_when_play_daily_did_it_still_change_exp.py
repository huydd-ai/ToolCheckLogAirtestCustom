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
lucky = LuckySpinPage()


def main():
    # TC22 -- TODO: Add description

    try:
        log_info("Start: tc22_kill_app")
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
        
        log_info("Start: get active mission for kill app test")
        active_ids = daily.get_active_mission_ids()
        if not active_ids:
            raise AssertionError("No active missions found to test kill app!")
        
        # Choose the easiest active mission instead of random
        mission_id = daily.get_easiest_mission_id(active_ids)
        db = daily._load_mission_db()
        mission_data = next((m for m in db if m["id"] == mission_id), None)
        mission_name = mission_data["ocr_text"]
        task_type = mission_data["task_type"]
        mission_data.get("target_item")
        
        log_info("End: get active mission for kill app test")
        log_info(f"Targeting mission for partial progress: [{mission_name}] (Type: {task_type})")
        
        mission_prog_before = daily.get_mission_progress(mission_name)
        
        import threading
        def _kill_app_later():
            sleep(35)
            log_info("Tearing down app MID-MISSION!")
            from pixon.common.test_flow import stop_app
            stop_app(config.GAME_PACKAGE)

        run_step("Play specific mission until killed", lambda: None)
        t = threading.Thread(target=_kill_app_later)
        t.daemon = True
        t.start()
        
        try:
            daily.execute_mission_logic(mission_id, game, home_page, partial=True)
        except Exception as e:
            log_info(f"Main thread mission stopped by kill app: {e}")
        t.join(timeout=5)
        teardown_app()
        run_step(
            "cold start app after kill mission",
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
        run_step("close popups after restart", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("tc22 open daily mission popup", daily.open_daily_mission_popup)
        
        active_ids_after = daily.get_active_mission_ids()
        if set(active_ids) != set(active_ids_after):
            raise AssertionError(f"Active missions changed after restart! Before: {active_ids}, After: {active_ids_after}")
            
        mission_prog_after = daily.get_mission_progress(mission_name)
        
        log_info(f"Start: Check Mission progress increased for [{mission_name}]")
        if mission_prog_after <= mission_prog_before:
            raise AssertionError(f"Result: Expected: Mission progress increased | Actual: Mission progress did not increase: {mission_prog_before}% -> {mission_prog_after}%")
        else:
            log_info(f"Result: Expected: Mission progress increased | Actual: Mission progress increased: {mission_prog_before}% -> {mission_prog_after}%")

        sleep(5)
        run_step("close popup", close_all_popups, home_page)
        log_info("End: tc22_kill_app")
    except Exception as e:
        wrapper.log_error(f"TC22_error: {str(e)}")
        snapshot(filename="tc22_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
