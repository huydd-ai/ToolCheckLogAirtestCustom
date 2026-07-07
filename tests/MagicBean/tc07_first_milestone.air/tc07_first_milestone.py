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
    # TC07 -- Cold start above the unlock threshold, cheat-win 1 level (below
    # milestone 1's 2 cumulative wins) and verify chest 1 is not Unlocked yet,
    # then cheat-win 1 more level (total 2) and verify milestone 1 opens:
    # chest 1 becomes Unlocked. There is no unclaimed-reward indicator on
    # real device, so chest state is the only checkable signal.

    try:
        log_info(f"Start: tc07_first_milestone (level {UNLOCK_LEVEL}, milestone 1 = {MILESTONE_1_WINS} wins)")

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

        log_info(f"Start: cheat-win {WINS_BEFORE_MILESTONE_1} level (below milestone 1)")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{WINS_BEFORE_MILESTONE_1}", cheat.cheat_magicbean_progress, wins=WINS_BEFORE_MILESTONE_1)
        log_info(f"End: cheat-win {WINS_BEFORE_MILESTONE_1} level (below milestone 1)")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {WINS_BEFORE_MILESTONE_1}")
        if not magic_bean.check_beanstalk_progress(WINS_BEFORE_MILESTONE_1):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {WINS_BEFORE_MILESTONE_1} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {WINS_BEFORE_MILESTONE_1} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {WINS_BEFORE_MILESTONE_1}")

        log_info("Start: Check chest not Unlocked yet after 1 win (below milestone 1 = 2 wins)")
        if magic_bean.is_chest_unlocked(timeout=3):
            raise AssertionError(
                "Result: Expected: chest 1 not Unlocked after 1 cumulative win (milestone 1 needs 2) | "
                "Actual: chest 1 Unlocked"
            )
        log_info(
            "Result: Expected: chest 1 not Unlocked after 1 cumulative win | Actual: chest 1 not Unlocked"
        )
        log_info("End: Check chest not Unlocked yet after 1 win (below milestone 1 = 2 wins)")

        log_info(f"Start: cheat-win {WINS_TO_REACH_MILESTONE_1} more level to reach milestone 1 (total {MILESTONE_1_WINS})")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{WINS_TO_REACH_MILESTONE_1}", cheat.cheat_magicbean_progress, wins=WINS_TO_REACH_MILESTONE_1)
        log_info(f"End: cheat-win {WINS_TO_REACH_MILESTONE_1} more level to reach milestone 1")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_1_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")

        log_info(f"Start: Check milestone 1 opens after {MILESTONE_1_WINS} cumulative wins")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                f"Result: Expected: chest 1 Unlocked after {MILESTONE_1_WINS} cumulative wins | "
                "Actual: chest 1 not Unlocked"
            )
        log_info(
            f"Result: Expected: chest 1 Unlocked after {MILESTONE_1_WINS} cumulative wins | "
            "Actual: chest 1 Unlocked"
        )
        log_info(f"End: Check milestone 1 opens after {MILESTONE_1_WINS} cumulative wins")

        sleep(5)
        log_info("End: tc07_first_milestone")
    except Exception as e:
        wrapper.log_error(f"TC07_error: {str(e)}")
        snapshot(filename="tc07_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
