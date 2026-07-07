from pixon.common import config
from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.daily_mission import DailyMissionPage
from pixon.pages.lucky_spin import LuckySpinPage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.common.test_flow import run_step, go_home_clean, teardown_app, close_all_popups
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_time_relative,
)


home_page = HomePage()
game = GamePage()
daily = DailyMissionPage()
lucky = LuckySpinPage()
heart_page = HeartSystemPage()


def main():
    # TC21 -- TODO: Add description

    try:
        log_info("Start: tc21_claim_all_exp")
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
        
        import random
        taps = random.randint(2, 10)
        log_info(f"Using trick: Tapping icon_ads_watch {taps} times")
        
        for i in range(taps):
            if not daily.wait_for_element(daily.icon_ads_watch, timeout=2):
                run_step("reopen daily mission popup for ads", daily.open_daily_mission_popup)
                sleep(1.5)
                
            log_info(f"Start: Check Tapping watch RV on attempt {i+1}")
            if not daily.wait_for_element(daily.icon_ads_watch, timeout=2):
                raise AssertionError(f"Failed to find watch RV on attempt {i+1}")
            daily.tap(daily.icon_ads_watch)
            sleep(10)
            
            exp = daily.get_exp_progress()
            log_info(f"Current EXP: {exp}")
            if exp >= 100:
                log_info("EXP reached 100, stopping trick early.")
                break

        for m in [30, 70, 100]:
            log_info(f"Start: Check Claim EXP milestone {m} reward")
            if not daily.claim_exp_reward(m):
                raise AssertionError(f"Result: Expected: Claimed EXP milestone {m} | Actual: Failed to claim EXP milestone {m} reward")
            else:
                log_info(f"Result: Expected: Claimed EXP milestone {m} | Actual: Claimed EXP milestone {m}")
            log_info(f"End: Claim EXP milestone {m} reward")
        sleep(10)
        log_info("End: tc21_claim_all_exp")
    except Exception as e:
        wrapper.log_error(f"TC21_error: {str(e)}")
        snapshot(filename="tc21_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
