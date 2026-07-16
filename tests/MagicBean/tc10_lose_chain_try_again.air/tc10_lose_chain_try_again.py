from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.pages.game_page import GamePage
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
game = GamePage()

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
    home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
    run_step("Go back homepage", go_home_clean, home_page)
    run_step("Close all popups", close_all_popups, home_page)


def cheat_wins(n):
    for i in range(n):
        run_step(f"enter level (win {i + 1}/{n})", home_page.tap, home_page.btn_main_play)
        sleep(8)
        run_step(f"force level result = win (win {i + 1}/{n})", set_param, "set_level_win", True)
        sleep(4)
        run_step("tap next", home_page.click_btn_next)
        sleep(8)
        run_step("Close all popups", close_all_popups, home_page)


def enter_level_and_lose():
    run_step("enter level", home_page.tap, home_page.btn_main_play)
    sleep(8)
    run_step("force level result = lose", set_param, "set_level_win", False)
    sleep(3)


def main():
    # TC10 -- Lose with streak >0, walk chain to popup 3, press "Try Again":
    # inter ads (fakeads) -> event popup + lose anim -> lands back inside a level.
    # Test Flow:
    # Step 1: Press Try Again, expect return into a level (not Home)
    #
    try:
        log_info("Start: tc10_lose_chain_try_again")
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
        
        # Verify we are in the game page by reading the level number via OCR
        try:
            current_lv = game.get_current_level()
            log_info(f"Result: Expected: in level page | Actual: in level {current_lv}")
        except Exception as e:
            raise AssertionError(
                f"Result: Expected: in level page after Try Again | Actual: failed to detect level ({e})"
            )

        log_info("End: tc10_lose_chain_try_again")
    except Exception as e:
        wrapper.log_error(f"TC10_error: {str(e)}")
        snapshot(filename="tc10_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
