from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.pages.remove_ads import RemoveAds
from pixon.pages.lucky_spin import LuckySpinPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
ads = RemoveAds()
lucky = LuckySpinPage()


def main():
    # TC05 -- TODO: Add description

    try:
        log_info("Start: tc05_notify_after_mission")
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
        run_step("complete tutorial from popup", lambda: daily.complete_tutorial_from_popup(close_after=False))

        active_ids = daily.get_active_mission_ids()
        if not active_ids:
            raise AssertionError("No active missions available to test notifications!")

        db = daily._load_mission_db()
        # Prefer missions that reliably complete quickly (avoid COLLECT_PIN and PLAY_TIME)
        preferred_ids = [m_id for m_id in active_ids if next((m for m in db if m["id"] == m_id), {}).get("task_type") not in ("COLLECT_PIN", "PLAY_TIME")]
        mission_id = preferred_ids[0] if preferred_ids else active_ids[0]

        mission_data = next((m for m in db if m["id"] == mission_id), None)
        mission_name = mission_data["ocr_text"] if mission_data else mission_id

        MAX_PLAY_ATTEMPTS = 5
        completable = False
        for attempt in range(1, MAX_PLAY_ATTEMPTS + 1):
            run_step(
                f"Play mission [{mission_name}] (attempt {attempt}/{MAX_PLAY_ATTEMPTS})",
                daily.execute_mission_logic, mission_id, game, home_page,
            )
            run_step("return home + close popups", close_all_popups, home_page)
            run_step("open daily mission popup to check completion", daily.open_daily_mission_popup)
            if daily.is_mission_completable(mission_id):
                completable = True
                log_info(
                    f"Mission [{mission_name}] completable after {attempt} attempt(s)"
                )
                run_step(
                    "close popup to verify home-screen notify",
                    lambda: daily.tap(daily.btn_close),
                )
                break
            log_info(
                f"Mission [{mission_name}] not yet complete after attempt {attempt}, replaying"
            )

        if not completable:
            raise AssertionError(
                f"Mission [{mission_name}] did not complete after {MAX_PLAY_ATTEMPTS} attempts"
            )

        log_info("Start: Check verify notify appears after mission completion")
        if not daily.is_notify_visible(timeout=8):
            raise AssertionError(
                f"Result: Expected: Notify visible after completing mission | Actual: Notify not visible after completing mission [{mission_name}]"
            )
        log_info(
            f"Result: Expected: Notify visible after completing mission | Actual: Notify visible after completing mission [{mission_name}]"
        )
        log_info("End: Check verify notify appears after mission completion")
        
        run_step("tc05 re-open daily mission popup", daily.open_daily_mission_popup)
        success = run_step(f"Verify and claim mission: [{mission_name}]", daily.verify_mission_and_claim, mission_id)
        if not success:
            raise AssertionError(f"Failed to verify and claim mission: {mission_name}")
            
        run_step("Claim any other collateral completed missions", daily.claim_all_other_completed_missions)
        run_step("Claim all exp milestone boxes", daily.claim_all_exp_boxes)
            
        run_step("Close daily mission popup", lambda: daily.tap(daily.btn_close))
        log_info("Start: Check Notify disappears after claiming")
        if not daily.is_notify_visible(timeout=5):
            raise AssertionError("Result: Expected: Notify not visible after claiming | Actual: Notify still visible after claiming")
        else:
            log_info(f"Result: Expected: Notify not visible after claiming | Actual: Notify not visible after claiming [{mission_name}]")
        log_info("End: Check Notify disappears after claiming")
        sleep(10)
        log_info("End: tc05_notify_after_mission")
    except Exception as e:
        wrapper.log_error(f"TC05_error: {str(e)}")
        snapshot(filename="tc05_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
