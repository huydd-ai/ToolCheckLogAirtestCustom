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
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
MILESTONE_1_WINS = 2   # milestone 1 at 2 cumulative wins
MILESTONE_2_WINS = 3   # +3 more wins -> total 5 = milestone 2


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


def wait_home():
    wait_for_app_ready()
    home_page.wait_for_element(home_page.splash_home_icon, timeout=30)
    run_step("Go back homepage", go_home_clean, home_page)
    run_step("Close all popups", close_all_popups, home_page)


def cheat_wins(n):
    run_step("open cheat console", cheat.open_cheat)
    run_step(f"cheat magicbean progress +{n}", cheat.cheat_magicbean_progress, wins=n)
    run_step("close cheat console", cheat.close_cheat)


def main():
    # TC11 -- Claim milestone 1, unlock milestone 2 (unclaimed), kill app
    # mid-level, reopen keeping data: claimed tick preserved, unclaimed chest
    # still Unlocked. No unclaimed-reward indicator exists on real device;
    # chest state is the only checkable signal.
    # Test Flow:
    # Step 1: Check claimed tick preserved
    # Step 2: Check unclaimed chest still Unlocked
    #
    try:
        log_info("Start: tc11_kill_app_preserves_rewards")
        boot()

        cheat_wins(MILESTONE_1_WINS)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)
        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(5)  # Wait for progress animation to finish
        magic_bean.tap_chest_at_level(MILESTONE_1_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        cheat_wins(MILESTONE_2_WINS)  # milestone 2 unlocked, unclaimed

        run_step("enter level", home_page.tap, home_page.btn_main_play)
        sleep(5)
        run_step("kill app mid-level", stop_app_only)
        sleep(3)

        # reopen checking persistence. Note server_sync=False so the device clock is trusted
        run_step(
            "reopen app keeping data",
            cold_start_with_combined,
            clear_data=False,
            server_sync=False,
            fakeads=True,
            playspeed=6,
        )
        sleep(15)
        wait_home()

        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(5)  # Wait for progress animation to finish

        log_info("Start: Check claimed tick preserved")
        if not magic_bean.is_chest_claimed(MILESTONE_1_WINS, timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 1 tick preserved | Actual: tick missing"
            )
        log_info("Result: Expected: milestone 1 tick preserved | Actual: preserved")

        log_info("Start: Check unclaimed chest still Unlocked")
        magic_bean.tap_chest_at_level(MILESTONE_2_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        log_info("Result: Expected: milestone 2 chest still Unlocked | Actual: tapped")

        log_info("End: tc11_kill_app_preserves_rewards")
    except Exception as e:
        wrapper.log_error(f"TC11_error: {str(e)}")
        snapshot(filename="tc11_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()

