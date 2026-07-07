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


def test_booster_group(item_names: list):
    run_step("Open daily mission popup", daily.open_daily_mission_popup)
    if daily.wait_for_element(daily.tap_to_continue, timeout=3):
        run_step("tap tap_to_continue", daily.tap, daily.tap_to_continue)

    target_task_type = "USE_BOOSTER"
    MAX_REROLLS = 25
    mission_data, found_item = daily.find_or_reroll_mission(target_task_type, target_items=item_names, home_page=home_page, max_rerolls=MAX_REROLLS)

    if not mission_data:
        raise AssertionError(f"No active mission of type {target_task_type} for {item_names} after {MAX_REROLLS} rerolls!")

    mission_id = mission_data["id"]
    mission_name = mission_data["ocr_text"]

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

    success = run_step(f"Verify visual progress and claim: [{mission_name}]", daily.verify_mission_and_claim, mission_id)
    if not success:
        raise AssertionError(f"Failed to verify visual progress update for mission: {mission_name}")

    run_step("close popup", close_all_popups, home_page)

    log_info(f"Start: Check Mission [{mission_name}] marked as complete & Verification")
    log_info(f"Result: Expected: Mission marked as complete | Actual: Mission [{mission_name}] successfully completed and verified")
    log_info(f"End: Check Mission [{mission_name}] marked as complete & Verification")
    sleep(10)
    log_info(f"End: tc15 successfully tested item [{found_item}] via [{mission_name}]")


def main():
    # TC15 -- TODO: Add description

    try:
        log_info("Start: tc15_use_booster_group")
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
        run_step("complete tutorial from popup", daily.complete_tutorial_from_popup)
        run_step("Back home after tutorial", go_home_clean, home_page)

        test_booster_group(["hammer", "drill", "magnet", "any_booster"])
        go_home_clean(home_page)

        #
        #
        #
        #

        sleep(10)
        log_info("End: tc15_use_booster_group")
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_use_booster_group_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
