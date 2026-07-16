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
    # TC10 -- TODO: Add description
    # Test Flow:
    # Step 1: Check In game after tapping Play
    #

    try:
        log_info("Start: tc10_play_main")
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

        run_step("Click Play", home_page.click_play)
        log_info("Start: Check In game after tapping Play")
        if not game.wait_for_element(game.booster[0], timeout=15):
            raise AssertionError("Result: Expected: In game | Actual: Not in game after tapping Play")
        else:
            log_info("Result: Expected: In game | Actual: In game")
        log_info("End: Check In game after tapping Play")
        sleep(10)
        log_info("End: tc10_play_main")
    except Exception as e:
        wrapper.log_error(f"TC10_error: {str(e)}")
        snapshot(filename="tc10_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
