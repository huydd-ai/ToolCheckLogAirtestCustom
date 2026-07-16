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
    # TC04 -- TODO: Add description
    # Test Flow:
    # Step 1: Check verify notify appears before joining
    #

    try:
        log_info("Start: tc04_check_icon_notify")
        run_step("tc04 advance to next day", set_time_relative, config.HOURS_TO_UNLOCK_DAILY_MISSIONS)

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

        log_info("Start: Check verify notify appears before joining")
        if not daily.is_notify_visible():
            raise AssertionError("Result: Expected: Notify visible on icon | Actual: Notify not visible on icon")
        else:
            log_info("Result: Expected: Notify visible on icon | Actual: Notify visible on icon")
        log_info("End: Check verify notify appears before joining")
        sleep(10)
        log_info("End: tc04_check_icon_notify")
    except Exception as e:
        wrapper.log_error(f"TC04_error: {str(e)}")
        snapshot(filename="tc04_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
