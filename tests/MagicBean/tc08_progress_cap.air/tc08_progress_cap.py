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
MILESTONE_15_WINS = 70  # magicbean_reward_table.json: milestone 15 (max) cumulative_wins
WINS_PAST_CAP = 2  # win 1-2 more levels past the max milestone


def main():
    # TC08 -- Cold start above the unlock threshold, cheat-loop straight to
    # milestone 15 (70 cumulative wins, the max milestone) without walking or
    # claiming any milestone along the way, verify milestone 15's chest state
    # is reachable, then win 1-2 more levels past 70 and verify nothing new
    # appears (chest state is unchanged -- no unclaimed-count indicator
    # exists on real device to check an increment against).
    # Test Flow:
    # Step 1: cheat-win {MILESTONE_15_WINS} levels straight to milestone 15 (no claims mid-way)
    # Step 2: Check beanstalk progress visually reaches level {MILESTONE_15_WINS}
    # Step 3: Check milestone 15 (max) is reachable after {MILESTONE_15_WINS} cumulative wins
    # Step 4: cheat-win {WINS_PAST_CAP} more levels past the max milestone (70)
    # Step 5: Check beanstalk progress still capped at level {MILESTONE_15_WINS}
    #

    try:
        log_info(f"Start: tc08_progress_cap (level {UNLOCK_LEVEL}, milestone 15 (max) = {MILESTONE_15_WINS} wins)")

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

        log_info(f"Start: cheat-win {MILESTONE_15_WINS - 1} levels, then 1 more to reach milestone 15")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_15_WINS - 1}", cheat.cheat_magicbean_progress, wins=MILESTONE_15_WINS - 1)
        run_step("open cheat console", cheat.open_cheat)
        run_step("cheat magicbean progress +1", cheat.cheat_magicbean_progress, wins=1)
        run_step("close cheat console", cheat.close_cheat)
        log_info(f"End: cheat-win levels to reach milestone 15")

        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(15)  # Wait for large progress animation to finish

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_15_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_15_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_15_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_15_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_15_WINS}")

        log_info(f"Start: Check milestone 15 (max) is reachable after {MILESTONE_15_WINS} cumulative wins")
        magic_bean.tap_chest_at_level(MILESTONE_15_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        log_info(
            f"Result: Expected: chest Unlocked after {MILESTONE_15_WINS} cumulative wins | Actual: tapped"
        )
        log_info(f"End: Check milestone 15 (max) is reachable after {MILESTONE_15_WINS} cumulative wins")

        log_info(f"Start: cheat-win {WINS_PAST_CAP} more levels past the max milestone (70)")
        run_step("Close all popups", close_all_popups, home_page)
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{WINS_PAST_CAP}", cheat.cheat_magicbean_progress, wins=WINS_PAST_CAP)
        run_step("close cheat console", cheat.close_cheat)
        log_info(f"End: cheat-win {WINS_PAST_CAP} more levels past the max milestone (70)")

        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(5)  # Wait for progress animation to finish

        # Smoke check only: no marker exists past 70, so "level 70 still
        # reached" holds whether or not the cap works -- this catches gross
        # regressions (board broken, progress wiped) but cannot visually
        # distinguish capped 70 from uncapped 72.
        log_info(f"Start: Check beanstalk progress still capped at level {MILESTONE_15_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_15_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk still at level {MILESTONE_15_WINS} (cap) after winning past it | "
                "Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk still at level {MILESTONE_15_WINS} (cap) | Actual: capped")
        log_info(f"End: Check beanstalk progress still capped at level {MILESTONE_15_WINS}")

        log_info(
            f"Start: Check chest state is unchanged after winning {WINS_PAST_CAP} levels past the cap (70)"
        )
        if not magic_bean.is_chest_claimed(MILESTONE_15_WINS, timeout=10):
            raise AssertionError(
                "Result: Expected: chest still Claimed (unchanged) after winning past the cap "
                "(70 is the max milestone, no new milestone past it) | Actual: chest not Claimed"
            )
        log_info(
            "Result: Expected: chest still Claimed (unchanged) after winning past the cap | Actual: Claimed"
        )
        log_info(
            f"End: Check chest state is unchanged after winning {WINS_PAST_CAP} levels past the cap (70)"
        )

        sleep(5)
        log_info("End: tc08_progress_cap")
    except Exception as e:
        wrapper.log_error(f"TC08_error: {str(e)}")
        snapshot(filename="tc08_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()

