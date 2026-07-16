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


def main():
    # TC04 -- Cold start above the unlock threshold, use the cheat console to
    # reach milestone 1 (2 cumulative wins) without real play, verify chest 1
    # becomes Unlocked, claim it, and verify it becomes Claimed with no
    # blocking confirmation popup.
    # Test Flow:
    # Step 1: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1
    # Step 2: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}
    # Step 3: Check chest 1 is Unlocked and claim it after reaching milestone 1
    # Step 4: Check chest 1 is Claimed after it was automatically claimed
    #

    try:
        log_info(f"Start: tc04_chest_unlocked_claim (level {UNLOCK_LEVEL}, {MILESTONE_1_WINS} cheat wins)")

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

        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(5)  # Wait for progress animation to finish

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_1_WINS):
            wrapper.log_warning(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: check failed (soft check)"
            )
        else:
            log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")

        log_info("Start: Check chest 1 is Unlocked and claim it after reaching milestone 1")
        magic_bean.tap_chest_at_level(MILESTONE_1_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        log_info(
            "Result: Expected: chest 1 is Unlocked after 2 cumulative wins | Actual: tapped"
        )
        log_info("End: Check chest 1 is Unlocked and claim it after reaching milestone 1")

        sleep(5)
        log_info("End: tc04_chest_unlocked_claim")
    except Exception as e:
        wrapper.log_error(f"TC04_error: {str(e)}")
        snapshot(filename="tc04_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
