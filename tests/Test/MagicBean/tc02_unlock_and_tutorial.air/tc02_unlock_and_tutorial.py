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

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL


def main():
    # TC02 -- Cold start at the Magic Bean unlock threshold, win a level, verify
    # the tutorial overlay appears, tap to continue (closes overlay -> starts
    # the event), then verify the icon opens the progress board.

    try:
        log_info(f"Start: tc02_unlock_and_tutorial (level {UNLOCK_LEVEL})")

        run_step(
            "cold start at unlock threshold",
            cold_start_with_combined,
            level=UNLOCK_LEVEL,
            **MagicBeanPage.DEFAULT_PROFILE,
        )
        sleep(15)
        wait_for_app_ready()
        for _ in range(15):
            try:
                if home_page.is_at_home():
                    break
            except Exception:
                pass
            sleep(2)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        run_step("enter level by clicking play", home_page.click_play)
        sleep(3)
        run_step("win level", set_param, "set_level_win", True)
        sleep(2)
        run_step("tap next to back home", home_page.click_btn_next)
        sleep(1)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Check Magic Bean tutorial overlay appears at unlock threshold")
        if not magic_bean.wait_for_element(magic_bean.popup_start_event, timeout=10):
            raise AssertionError(
                f"Result: Expected: tutorial overlay appears at lv{UNLOCK_LEVEL} | Actual: overlay did not appear"
            )
        log_info(
            f"Result: Expected: tutorial overlay appears at lv{UNLOCK_LEVEL} | Actual: overlay appeared"
        )
        log_info("End: Check Magic Bean tutorial overlay appears at unlock threshold")

        # New lv33 behavior: tapping tap_to_continue closes the overlay and
        # that action STARTS the event (no separate Start button; close =
        # start). The progress board is NOT shown yet -- it opens via the icon.
        run_step("tap to continue (closes overlay, starts event)", magic_bean.tap, magic_bean.tap_to_continue)
        sleep(2)
        run_step("Close all popups", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)

        log_info("Start: Check icon opens progress board after start")
        if not magic_bean.open_event_popup(timeout=10):
            raise AssertionError(
                "Result: Expected: Magic Bean icon opens progress board after start | "
                "Actual: board did not open"
            )
        log_info("Result: Expected: icon opens progress board | Actual: board opened")
        log_info("End: Check icon opens progress board after start")

        run_step("close event board", magic_bean.tap, magic_bean.btn_close)
        sleep(2)
        run_step("Close all popups", close_all_popups, home_page)

        sleep(5)
        log_info("End: tc02_unlock_and_tutorial")
    except Exception as e:
        wrapper.log_error(f"TC02_error: {str(e)}")
        snapshot(filename="tc02_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
