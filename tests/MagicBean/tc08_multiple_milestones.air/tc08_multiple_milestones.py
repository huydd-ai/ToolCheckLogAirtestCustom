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
MILESTONE_2_WINS = 5  # magicbean_reward_table.json: milestone 2 cumulative_wins
WINS_TO_REACH_MILESTONE_2 = MILESTONE_2_WINS - MILESTONE_1_WINS  # 3 more wins after milestone 1 (2 -> 5)


def main():
    # TC08 -- Cold start above the unlock threshold, cheat-win to milestone 1
    # (2 cumulative wins), claim it, then continue cheat-winning to milestone 2
    # (5 cumulative wins) without claiming, and verify chest state transitions
    # from "nothing unclaimed" to "milestone 2 Unlocked". There is no
    # unclaimed-reward count indicator on real device, so this checks the
    # False->True chest-state transition instead of a badge count increment.
    # This is a representative walk across only milestones 1 and 2, not all 15.

    try:
        log_info(
            f"Start: tc08_multiple_milestones (level {UNLOCK_LEVEL}, "
            f"milestone 1 = {MILESTONE_1_WINS} wins, milestone 2 = {MILESTONE_2_WINS} wins)"
        )

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

        log_info(f"Start: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_1_WINS}", cheat.cheat_magicbean_progress, wins=MILESTONE_1_WINS)
        log_info(f"End: cheat-win {MILESTONE_1_WINS} levels to reach milestone 1")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_1_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_1_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_1_WINS}")

        log_info(f"Start: Check chest 1 is Unlocked after reaching milestone 1 ({MILESTONE_1_WINS} wins)")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                f"Result: Expected: chest 1 Unlocked after {MILESTONE_1_WINS} cumulative wins | "
                "Actual: chest 1 not Unlocked"
            )
        log_info(
            f"Result: Expected: chest 1 Unlocked after {MILESTONE_1_WINS} cumulative wins | "
            "Actual: chest 1 Unlocked"
        )
        log_info(f"End: Check chest 1 is Unlocked after reaching milestone 1 ({MILESTONE_1_WINS} wins)")

        log_info("Start: Claim milestone 1 chest")
        claimed_ok = magic_bean.claim_chest()
        if not claimed_ok:
            raise AssertionError(
                "Result: Expected: claim_chest() succeeds for milestone 1 | Actual: returned False"
            )
        log_info("Result: Expected: claim_chest() succeeds for milestone 1 | Actual: True")
        log_info("End: Claim milestone 1 chest")

        # claim_chest()'s trailing btn_close tap may drop the event board, so
        # re-open it before reading the baseline chest state.
        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info("Start: Check no Unlocked chest remains right after claiming milestone 1")
        baseline_unlocked = magic_bean.is_chest_unlocked(timeout=3)
        if baseline_unlocked:
            raise AssertionError(
                "Result: Expected: no Unlocked chest right after claiming milestone 1 (milestone 2 not reached yet) | "
                "Actual: an Unlocked chest is present"
            )
        log_info(
            "Result: Expected: no Unlocked chest right after claiming milestone 1 | Actual: none found"
        )
        log_info("End: Check no Unlocked chest remains right after claiming milestone 1")

        log_info(
            f"Start: cheat-win {WINS_TO_REACH_MILESTONE_2} more levels to reach milestone 2 "
            f"(total {MILESTONE_2_WINS})"
        )
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{WINS_TO_REACH_MILESTONE_2}", cheat.cheat_magicbean_progress, wins=WINS_TO_REACH_MILESTONE_2)
        log_info(f"End: cheat-win {WINS_TO_REACH_MILESTONE_2} more levels to reach milestone 2")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_2_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_2_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_2_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_2_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_2_WINS}")

        log_info(
            f"Start: Check chest becomes Unlocked after reaching milestone 2 ({MILESTONE_2_WINS} cumulative wins)"
        )
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: an Unlocked chest after reaching milestone 2 (was none right after claiming "
                "milestone 1) | Actual: no Unlocked chest found"
            )
        log_info(
            "Result: Expected: an Unlocked chest after reaching milestone 2 (was none right after claiming "
            "milestone 1) | Actual: found"
        )
        log_info(
            f"End: Check chest becomes Unlocked after reaching milestone 2 ({MILESTONE_2_WINS} cumulative wins)"
        )

        sleep(5)
        log_info("End: tc08_multiple_milestones")
    except Exception as e:
        wrapper.log_error(f"TC08_error: {str(e)}")
        snapshot(filename="tc08_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
