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
MILESTONE_3_WINS = 10  # magicbean_reward_table.json: milestone 3 cumulative_wins

# Reward table entries under test (magicbean_reward_table.json), confirmed
# offline via MagicBeanPage.validate_reward_against_db against the real file:
#   milestone 1: coins=20,  items={"money": 20}
#   milestone 2: coins=80,  items={"drill": 1}
#   milestone 3: coins=120, items={"hammer": 1, "heart": 15}
REWARD_CHECKS = [
    (1, 20, {"money": 20}),
    (2, 80, {"drill": 1}),
    (3, 120, {"hammer": 1, "heart": 15}),
]


def main():
    # TC06 -- Cold start above the unlock threshold, cheat-loop to milestone 3
    # (10 cumulative wins) without claiming anything, verify an unclaimed
    # chest is waiting, claim milestones sequentially (there is no unclaimed
    # count indicator on real device -- only Locked/Unlocked/Claimed chest
    # state is checkable), and validate expected reward constants against
    # magicbean_reward_table.json (data consistency, no screen read).

    try:
        log_info(f"Start: tc06_badge_and_reward_content (level {UNLOCK_LEVEL}, {MILESTONE_3_WINS} cheat wins)")

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

        log_info(f"Start: cheat-win {MILESTONE_3_WINS} levels to reach milestone 3 (no claims yet)")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_3_WINS}", cheat.cheat_magicbean_progress, wins=MILESTONE_3_WINS)
        log_info(f"End: cheat-win {MILESTONE_3_WINS} levels to reach milestone 3")

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_3_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_3_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_3_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_3_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_3_WINS}")

        log_info("Start: Check an unclaimed chest is waiting after reaching milestone 3")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: at least one Unlocked (unclaimed) chest after reaching milestone 3 | "
                "Actual: no Unlocked chest found"
            )
        log_info(
            "Result: Expected: at least one Unlocked (unclaimed) chest after reaching milestone 3 | "
            "Actual: found"
        )
        log_info("End: Check an unclaimed chest is waiting after reaching milestone 3")

        # Claim milestone 1's chest, then milestone 2's, sequentially. Note:
        # claim_chest() has no milestone selector -- it taps whichever chest
        # currently matches chest_unlocked -- so ordering across the two calls
        # relies on the board presenting the lowest unclaimed milestone first.
        # capture-time TODO: verify chest-tap targeting/scroll order once a
        # real build/board layout is available. Also verify claim_chest()'s
        # trailing btn_close tap doesn't dismiss the whole event board (rather
        # than just a reward overlay) between sequential claims -- if it does,
        # the second claim_chest() call would find no chest_unlocked to tap.
        for step_num in (1, 2):
            log_info(f"Start: Claim milestone {step_num} chest")
            claimed_ok = magic_bean.claim_chest()
            if not claimed_ok:
                raise AssertionError(
                    f"Result: Expected: claim_chest() succeeds for milestone {step_num} | Actual: returned False"
                )
            sleep(2)
            log_info(f"Result: Expected: claim_chest() succeeds for milestone {step_num} | Actual: True")
            log_info(f"End: Claim milestone {step_num} chest")

        # milestone 3 (reached at 10 wins) was never claimed above -- an
        # Unlocked chest must still be waiting.
        log_info("Start: Check milestone 3 chest is still Unlocked after claiming milestones 1 and 2")
        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 3 chest still Unlocked (never claimed) | Actual: no Unlocked chest found"
            )
        log_info(
            "Result: Expected: milestone 3 chest still Unlocked (never claimed) | Actual: found"
        )
        log_info("End: Check milestone 3 chest is still Unlocked after claiming milestones 1 and 2")

        # Data-consistency check only: compares expected constants against the
        # reward-table JSON. It does NOT read the screen -- an on-device
        # reward/display mismatch is not caught here.
        log_info("Start: Validate expected rewards against magicbean_reward_table.json")
        for milestone, expected_coins, expected_items in REWARD_CHECKS:
            ok, reason = magic_bean.validate_reward_against_db(
                milestone=milestone,
                expected_coins=expected_coins,
                expected_items=expected_items,
            )
            if (ok, reason) != (True, "ok"):
                raise AssertionError(
                    f"Result: Expected: milestone {milestone} reward matches db (coins={expected_coins}, "
                    f"items={expected_items}) -> (True, 'ok') | Actual: ({ok}, {reason})"
                )
            log_info(
                f"Result: Expected: milestone {milestone} reward matches db (coins={expected_coins}, "
                f"items={expected_items}) -> (True, 'ok') | Actual: ({ok}, {reason})"
            )
        log_info("End: Validate expected rewards against magicbean_reward_table.json")

        sleep(5)
        log_info("End: tc06_badge_and_reward_content")
    except Exception as e:
        wrapper.log_error(f"TC06_error: {str(e)}")
        snapshot(filename="tc06_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
