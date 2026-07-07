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

    # TC06 -- TODO: Add description

    try:
        log_info("Start: tc06_random_mission")
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
        count_a = daily.get_mission_count()
        count_b = daily.get_collect_mission_count()
        total_missions = count_a + count_b
        log_info("Start: Check Expected 5 missions")
        if total_missions != 5:
            # Maybe some missions are already completed (COLLECT)
            claimable_ids = daily.get_claimable_mission_ids()
            for m_id in claimable_ids:
                daily.verify_mission_and_claim(m_id)
            daily.tap(daily.btn_close)
            daily.open_daily_mission_popup()
            # After claiming, they disappear or become claimed, so total count logic needs OCR if we really want to recount.
            # But normally count_a + count_b == 5 before claiming.
            
        if total_missions != 5:
            raise AssertionError(f"Result: Expected: 5 missions | Actual: {total_missions} missions (PLAY: {count_a}, COLLECT: {count_b})")
        else:
            log_info(f"Result: Expected: 5 missions | Actual: {count_a} missions")
        log_info("End: Check Expected 5 missions")
        sleep(10)
        log_info("End: tc06_random_mission")
    except Exception as e:
        wrapper.log_error(f"TC06_error: {str(e)}")
        snapshot(filename="tc06_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
