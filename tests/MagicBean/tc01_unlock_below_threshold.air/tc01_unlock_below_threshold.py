from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_param,
    wait_for_app_ready,
)


home_page = HomePage()
magic_bean = MagicBeanPage()

BELOW_THRESHOLD_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL - 1


def main():
    # TC01 -- Cold start at lv32, win the 2-phase level to reach lv33 (unlock
    # threshold), back home, tap the Magic Bean icon, dismiss the tutorial
    # overlay, and verify the event board opens.
    # Test Flow:
    # Step 1: win 2-phase lv{BELOW_THRESHOLD_LEVEL} to reach lv{MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL}
    # Step 2: close all popups
    # Step 3: tap icon -> confirm board via event_board_character img
    #

    try:
        log_info(f"Start: tc01_unlock_below_threshold (level {BELOW_THRESHOLD_LEVEL})")

        run_step(
            "cold start below threshold",
            cold_start_with_combined,
            level=BELOW_THRESHOLD_LEVEL,
            **MagicBeanPage.DEFAULT_PROFILE,
        )
        sleep(15)
        wait_for_app_ready()
        home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        # Setup: lv32 has 2 phases that auto-chain in-level -- win both to
        # complete the level and reach lv33 (unlock threshold).
        log_info(f"Start: win 2-phase lv{BELOW_THRESHOLD_LEVEL} to reach lv{MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL}")
        run_step("enter level by clicking play", home_page.click_play)
        for phase in range(2):
            sleep(3)
            run_step(f"win level phase {phase + 1}/2", set_param, "set_level_win", True)
            sleep(2)
        run_step("tap next to back home", home_page.click_btn_next)
        sleep(1)
        run_step("Close all popups", close_all_popups, home_page)
        log_info(f"End: win 2-phase lv{BELOW_THRESHOLD_LEVEL}")

        run_step("Go back homepage", go_home_clean, home_page)

        # New lv33 behavior: popup storm. No need to check tutorial, just close all popups.
        log_info("Start: close all popups")
        run_step("Close all popups", close_all_popups, home_page)
        log_info("End: close all popups")

        # Re-open via the Magic Bean icon and confirm the event board opened by
        # matching the character image (event_board_character).
        log_info("Start: tap icon -> confirm board via event_board_character img")
        opened = run_step("open event via icon", magic_bean.open_event_popup)
        assert opened and magic_bean.wait_for_element(magic_bean.event_board, timeout=5), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        magic_bean.tap(magic_bean.btn_close)
        log_info("Result: Expected: board confirmed via event_board_character | Actual: confirmed")
        log_info("End: confirm board open")

        sleep(5)
        log_info("End: tc01_unlock_below_threshold")
    except Exception as e:
        wrapper.log_error(f"TC01_error: {str(e)}")
        snapshot(filename="tc01_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
