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

        # New lv33 behavior: popup storm incl. Magic Bean popup with tutorial
        # overlay on top. verify_unlock_flow taps through the tutorial, checks
        # the event board, closes all popups, then taps the icon and checks
        # the board opens.
        log_info("Start: verify unlock flow (tutorial -> board -> popups closed -> icon)")
        flow_ok = run_step("verify unlock flow", magic_bean.verify_unlock_flow, home_page)
        assert flow_ok, (
            "Result: Expected: first-unlock tutorial overlay auto-shows at lv33 | "
            "Actual: no tutorial overlay appeared"
        )
        log_info("Result: Expected: unlock flow verified (tutorial, board, icon) | Actual: verified")
        log_info("End: verify unlock flow")

        sleep(5)
        log_info("End: tc01_unlock_below_threshold")
    except Exception as e:
        wrapper.log_error(f"TC01_error: {str(e)}")
        snapshot(filename="tc01_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
