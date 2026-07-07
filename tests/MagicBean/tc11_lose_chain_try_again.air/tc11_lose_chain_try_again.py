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
MILESTONE_1_WINS = 2


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


def cheat_wins(n):
    for i in range(n):
        run_step(f"open cheat console (win {i + 1}/{n})", cheat.open_cheat)
        run_step(f"cheat win level {i + 1}/{n}", cheat.win_level_and_continue)
        sleep(1)


def enter_level_and_lose():
    run_step("enter level", home_page.tap, home_page.btn_main_play)
    sleep(4)
    run_step("autoplay on", set_autoplay, True, 6)
    sleep(4)
    run_step("force level result = lose", set_param, "set_level_win", False)
    sleep(3)
    run_step("autoplay off", set_autoplay, False)


def main():
    # TC11 -- Lose with streak >0, walk chain to popup 3, press "Try Again":
    # inter ads (fakeads) -> event popup + lose anim -> lands back inside a level.
    try:
        log_info("Start: tc11_lose_chain_try_again")
        boot()
        cheat_wins(MILESTONE_1_WINS)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        enter_level_and_lose()

        if not magic_bean.wait_for_element(magic_bean.lose_popup_1, timeout=15):
            raise AssertionError("Result: Expected: lose popup 1 visible | Actual: not found")
        magic_bean.tap(magic_bean.btn_close)
        sleep(2)
        if not magic_bean.wait_for_element(magic_bean.lose_popup_2, timeout=10):
            raise AssertionError("Result: Expected: lose popup 2 visible | Actual: not found")
        magic_bean.tap(magic_bean.btn_close)
        sleep(2)
        if not magic_bean.wait_for_element(magic_bean.lose_popup_3, timeout=10):
            raise AssertionError("Result: Expected: lose popup 3 visible | Actual: not found")

        log_info("Start: Press Try Again, expect return into a level (not Home)")
        magic_bean.tap(magic_bean.btn_try_again)
        sleep(12)  # inter ads + event popup lose anim + level load

        # The tap must actually consume the popup -- "not at home" alone also
        # holds when the tap missed and popup 3 is still on screen.
        if magic_bean.wait_for_element(magic_bean.lose_popup_3, timeout=3):
            raise AssertionError(
                "Result: Expected: lose popup 3 dismissed after Try Again | Actual: popup still visible (tap missed)"
            )

        at_home = home_page.is_at_home()
        if at_home:
            raise AssertionError(
                "Result: Expected: user lands inside a level after Try Again | Actual: at Home"
            )
        log_info("Result: Expected: user lands inside a level after Try Again | Actual: in level")

        log_info("End: tc11_lose_chain_try_again")
    except Exception as e:
        wrapper.log_error(f"TC11_error: {str(e)}")
        snapshot(filename="tc11_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
