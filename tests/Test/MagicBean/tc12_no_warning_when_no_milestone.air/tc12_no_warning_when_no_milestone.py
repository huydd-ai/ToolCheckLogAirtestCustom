from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
    set_autoplay,
    set_param,
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL


def boot():
    run_step(
        "cold start above unlock threshold",
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
    run_step(
        "verify unlock flow (tutorial -> board -> popups -> icon)",
        magic_bean.verify_unlock_flow,
        home_page,
    )


def enter_level_and_lose():
    run_step("enter level", home_page.tap, home_page.btn_main_play)
    sleep(4)
    run_step("autoplay on", set_autoplay, True, 6)
    sleep(4)
    run_step("force level result = lose", set_param, "set_level_win", False)
    sleep(3)
    run_step("autoplay off", set_autoplay, False)


def main():
    # TC12 -- Fresh event state (streak 0, no milestone reached): losing must
    # NOT show the progress-loss warning popup (lose_popup_2).
    try:
        log_info("Start: tc12_no_warning_when_no_milestone")
        boot()
        # no cheat wins -- streak stays 0

        enter_level_and_lose()

        if not magic_bean.wait_for_element(magic_bean.lose_popup_1, timeout=15):
            raise AssertionError("Result: Expected: lose popup 1 visible | Actual: not found")
        magic_bean.tap(magic_bean.btn_close)
        sleep(3)

        log_info("Start: Check progress-loss warning is ABSENT with streak 0")
        if magic_bean.wait_for_element(magic_bean.lose_popup_2, timeout=4):
            raise AssertionError(
                "Result: Expected: no progress-loss warning when streak=0 | Actual: lose popup 2 shown"
            )
        log_info("Result: Expected: no progress-loss warning when streak=0 | Actual: absent")

        run_step("Close remaining popups", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("End: tc12_no_warning_when_no_milestone")
    except Exception as e:
        wrapper.log_error(f"TC12_error: {str(e)}")
        snapshot(filename="tc12_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
