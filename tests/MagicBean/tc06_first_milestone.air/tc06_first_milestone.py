from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
)


home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
MILESTONE_1_WINS = 2  # magicbean_reward_table.json: milestone 1 cumulative_wins
WINS_BEFORE_MILESTONE_1 = 1  # 1 win: below milestone 1 (2), no badge/chest yet
WINS_TO_REACH_MILESTONE_1 = MILESTONE_1_WINS - WINS_BEFORE_MILESTONE_1  # 1 more win -> total 2


def main():
    # TC06 -- Cold start above the unlock threshold, cheat-win {MILESTONE_1_WINS} levels
    # to reach milestone 1 and verify milestone 1 opens.
    # There is no unclaimed-reward indicator on real device, so chest state is the only checkable signal.
    # Test Flow:
    # Step 1: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1
    # Step 2: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}
    # Step 3: Check milestone 1 opens after {MILESTONE_1_WINS} cumulative wins
    #

    try:
        log_info(f"Start: tc06_first_milestone (level {UNLOCK_LEVEL}, milestone 1 = {MILESTONE_1_WINS} wins)")

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

        log_info(f"Start: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_1_WINS}", cheat.cheat_magicbean_progress, wins=MILESTONE_1_WINS)
        run_step("close cheat console", cheat.close_cheat)
        log_info(f"End: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1")

        log_info("Start: tap icon -> confirm board via event_board_character img")
        opened = run_step("open event via icon", magic_bean.open_event_popup)
        assert opened and magic_bean.wait_for_element(magic_bean.event_board, timeout=5), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        log_info("Result: Expected: board confirmed via event_board_character | Actual: confirmed")
        log_info("End: confirm board open")
        sleep(5)  # Wait for progress animation to finish

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_1_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")

        log_info(f"Start: Check milestone 1 opens after {MILESTONE_1_WINS} cumulative wins")
        assert magic_bean.tap_chest_at_level(MILESTONE_1_WINS), f"Failed to tap chest for milestone 1 at win {MILESTONE_1_WINS}"
        assert home_page.wait_for_element(home_page.tap_to_claim, timeout=8), "tap_to_claim did not appear for milestone 1"
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        log_info(
            f"Result: Expected: chest 1 Unlocked after {MILESTONE_1_WINS} cumulative wins | "
            "Actual: tapped"
        )
        log_info(f"End: Check milestone 1 opens after {MILESTONE_1_WINS} cumulative wins")

        sleep(5)
        log_info("End: tc06_first_milestone")
    except Exception as e:
        wrapper.log_error(f"TC06_error: {str(e)}")
        snapshot(filename="tc06_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()

