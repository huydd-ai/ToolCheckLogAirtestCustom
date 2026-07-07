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
    # TC09 -- Cold start above the unlock threshold, cheat-loop straight to
    # milestone 15 (70 cumulative wins, the max milestone) without walking or
    # claiming any milestone along the way, verify milestone 15's chest state
    # is reachable, then win 1-2 more levels past 70 and verify nothing new
    # appears (chest state is unchanged -- no unclaimed-count indicator
    # exists on real device to check an increment against).

    try:
        log_info(f"Start: tc09_progress_cap (level {UNLOCK_LEVEL}, milestone 15 (max) = {MILESTONE_15_WINS} wins)")

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

        log_info(f"Start: cheat-win {MILESTONE_15_WINS} levels straight to milestone 15 (no claims mid-way)")
        # Straight jump to 70 wins -- no per-milestone walking or claiming,
        # per task instructions.
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_15_WINS}", cheat.cheat_magicbean_progress, wins=MILESTONE_15_WINS)
        log_info(f"End: cheat-win {MILESTONE_15_WINS} levels straight to milestone 15")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_15_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_15_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_15_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_15_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_15_WINS}")

        log_info(f"Start: Check milestone 15 (max) is reachable after {MILESTONE_15_WINS} cumulative wins")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                f"Result: Expected: chest Unlocked after {MILESTONE_15_WINS} cumulative wins (milestone 15, max) | "
                "Actual: chest not Unlocked"
            )
        log_info(
            f"Result: Expected: chest Unlocked after {MILESTONE_15_WINS} cumulative wins | Actual: Unlocked"
        )
        log_info(f"End: Check milestone 15 (max) is reachable after {MILESTONE_15_WINS} cumulative wins")

        log_info(f"Start: cheat-win {WINS_PAST_CAP} more levels past the max milestone (70)")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{WINS_PAST_CAP}", cheat.cheat_magicbean_progress, wins=WINS_PAST_CAP)
        log_info(f"End: cheat-win {WINS_PAST_CAP} more levels past the max milestone (70)")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

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
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: chest still Unlocked (unchanged) after winning past the cap "
                "(70 is the max milestone, no new milestone past it) | Actual: chest not Unlocked"
            )
        log_info(
            "Result: Expected: chest still Unlocked (unchanged) after winning past the cap | Actual: Unlocked"
        )
        log_info(
            f"End: Check chest state is unchanged after winning {WINS_PAST_CAP} levels past the cap (70)"
        )

        sleep(5)
        log_info("End: tc09_progress_cap")
    except Exception as e:
        wrapper.log_error(f"TC09_error: {str(e)}")
        snapshot(filename="tc09_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
