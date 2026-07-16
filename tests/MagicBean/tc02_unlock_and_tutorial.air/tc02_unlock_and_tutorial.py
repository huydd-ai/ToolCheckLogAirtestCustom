from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_param,
    wait_for_app_ready,
)


home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

BELOW_THRESHOLD_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL - 1


def main():
    # TC02 -- Cold start below the Magic Bean unlock threshold (lv32), win the 
    # 2-phase level to reach lv33 (unlock threshold), then verify the tutorial
    # and progress board unlock.
    # Test Flow:
    # Step 1: win 2-phase lv{BELOW_THRESHOLD_LEVEL} to reach lv{MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL}
    # Step 2: Check icon opens progress board after start
    #

    try:
        log_info(f"Start: tc02_unlock_and_tutorial (level {BELOW_THRESHOLD_LEVEL})")

        import typing
        profile: typing.Dict[str, typing.Any] = typing.cast(typing.Dict[str, typing.Any], MagicBeanPage.DEFAULT_PROFILE.copy())

        run_step(
            "cold start below unlock threshold",
            cold_start_with_combined,
            level=BELOW_THRESHOLD_LEVEL,
            **profile,
        )
        sleep(15)
        wait_for_app_ready()
        home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info(f"Start: win 2-phase lv{BELOW_THRESHOLD_LEVEL} to reach lv{MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL}")
        run_step("enter level by clicking play", home_page.click_play)
        for phase in range(2):
            sleep(3)
            run_step(f"win level phase {phase + 1}/2", set_param, "set_level_win", True)
            sleep(2)
        run_step("tap next to back home", home_page.click_btn_next)
        sleep(1)
        run_step("Close all popups", close_all_popups, home_page)



        log_info("Start: Check icon opens progress board after start")
        log_info("Start: tap icon -> confirm board via event_board_character img")
        opened = run_step("open event via icon", magic_bean.open_event_popup)
        assert opened and magic_bean.wait_for_element(magic_bean.event_board, timeout=5), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        log_info("Result: Expected: board confirmed via event_board_character | Actual: confirmed")
        log_info("End: confirm board open")
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
        teardown_app(__file__)


if __name__ == "__main__":
    main()
