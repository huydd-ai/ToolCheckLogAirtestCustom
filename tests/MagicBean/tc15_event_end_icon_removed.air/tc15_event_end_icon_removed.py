from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app, stop_app_only
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
    set_time_relative,
    restore_system_time,
    set_param,
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
EVENT_DURATION_HOURS = 168.0


def boot():
    run_step(
        "cold start above unlock threshold",
        cold_start_with_combined,
        level=UNLOCK_LEVEL,
        **MagicBeanPage.DEFAULT_PROFILE,
    )
    sleep(15)
    wait_for_app_ready()
    home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
    run_step("Go back homepage", go_home_clean, home_page)
    run_step("Close all popups", close_all_popups, home_page)


def main():
    # TC15 -- Event ended, nothing left to claim: after playing exactly one
    # level and returning Home, the event icon is removed.
    # Test Flow:
    # Step 1: Play one level, expect icon removed on return
    #
    try:
        log_info("Start: tc15_event_end_icon_removed")
        run_step("restore device clock to real time", restore_system_time)
        boot()  # no wins -> nothing to claim at end

        run_step("kill app before time jump", stop_app_only)
        run_step("advance clock past event duration", set_time_relative, EVENT_DURATION_HOURS + 1)
        run_step(
            "reopen app keeping data",
            cold_start_with_combined,
            clear_data=False,
            server_sync=False,
            fakeads=True,
            playspeed=6,
        )
        sleep(15)
        wait_for_app_ready()
        home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
        run_step("Close end-of-event popups", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Play one level, expect icon removed on return")
        run_step("enter level", home_page.tap, home_page.btn_main_play)
        sleep(8)
        run_step("force level result = win", set_param, "set_level_win", True)
        sleep(4)
        run_step("tap next", home_page.click_btn_next)
        sleep(8)
        run_step("Close all popups", close_all_popups, home_page)

        if magic_bean.is_event_icon_visible(timeout=5):
            raise AssertionError(
                "Result: Expected: event icon removed after 1 level post-end | Actual: icon still visible"
            )
        log_info("Result: Expected: event icon removed after 1 level post-end | Actual: removed")

        log_info("End: tc15_event_end_icon_removed")
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_error.png")
    finally:
        restore_system_time()
        teardown_app(__file__)


if __name__ == "__main__":
    main()
