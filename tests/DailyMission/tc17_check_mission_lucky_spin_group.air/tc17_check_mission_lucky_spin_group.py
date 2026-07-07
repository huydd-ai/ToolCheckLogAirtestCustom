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
    # TC17 -- TODO: Add description

    try:
        log_info("Start: tc17_lucky_spin_group")


        run_step("advance 3 days to unlock lucky spin", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)
        run_step(
            "cold start with parameters",
            cold_start_with_combined,
            heart=5, level=12, coin=1000, fakeads=True, playspeed=6,
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
        if daily.wait_for_element(daily.tap_to_continue, timeout=3):
            run_step("tap tap_to_continue", daily.tap, daily.tap_to_continue)

        target_task_type = "COMPLETE_SPIN"
        MAX_REROLLS = 15
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
        while attempt < max_attempts:
            run_step("Reopen daily mission popup if needed", daily.open_daily_mission_popup)
            sleep(2)  # Wait for UI text to fully render before OCR
            if daily.is_mission_completable(mission_id):
                log_info(f"Mission {mission_name} is completable!")
                break
            
            # Find the row for this mission and tap the play button
            screen = wrapper.get_screen()
            row = daily._find_mission_row(screen, mission_name, [daily.btn_play_daily, daily.btn_collect])
            
            if row is not None and row["tmpl"] is daily.btn_play_daily:
                daily.tap(row["pos"])
                lucky.wait_for_element(lucky.label_lucky_spin, timeout=10)
                
                if attempt > 0:
                    if attempt > 3:
                        log_info("Reached max of 3 ad spins a day, stopping spins.")
                        break
                    
                    # After the first free spin, subsequent spins require watching an ad (max 3 times).
                    if daily.wait_for_element(daily.icon_ads_watch, timeout=8):
                        log_info(f"Watching ad for spin turn (Ad spin #{attempt})")
                        daily.tap(daily.icon_ads_watch)
                        sleep(20)  # wait for ad to complete
                    else:
                        log_info(f"Ad button not found on attempt {attempt} — no free ad spin available, exiting loop")
                        break
                else:
                    log_info("First time spin: using free spin")
                    lucky.spin()
                
                # it will spin so sleep 6s to allow animation to finish before closing
                sleep(6)
                run_step("close lucky spin", close_all_popups, home_page)
            elif row is not None and row["tmpl"] is daily.btn_collect:
                log_info(f"Mission {mission_name} shows COLLECT, ready to claim")
                break
            else:
                log_info(f"Fallback Play mission: [{mission_name}] (Attempt {attempt + 1})")
                run_step(f"Play mission fallback: [{mission_name}]", daily.execute_mission_logic, mission_id, game, home_page)
                
            attempt += 1
            
        run_step("Reopen daily mission popup if needed for final check", daily.open_daily_mission_popup)
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
        log_info(f"End: tc17_lucky_spin_group successfully tested [{mission_name}]")
    except Exception as e:
        wrapper.log_error(f"TC17_error: {str(e)}")
        snapshot(filename="tc17_lucky_spin_group_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
