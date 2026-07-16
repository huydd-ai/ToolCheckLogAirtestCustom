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
MILESTONE_1_WINS = 2
MILESTONE_2_WINS = 5
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
    # TC05 -- Cold start above the unlock threshold, cheat-loop to milestone 3
    # (10 cumulative wins) without claiming anything, verify an unclaimed
    # chest is waiting, claim milestones sequentially (there is no unclaimed
    # count indicator on real device -- only Locked/Unlocked/Claimed chest
    # state is checkable), and validate expected reward constants against
    # magicbean_reward_table.json (data consistency, no screen read).
    # Test Flow:
    # Step 1: cheat-win {MILESTONE_3_WINS} levels to reach milestone 3 (no claims yet)
    # Step 2: Check beanstalk progress visually reaches level {MILESTONE_3_WINS}
    # Step 3: Claim milestone {step_num} chest
    # Step 4: Check milestone 3 chest is Unlocked after claiming milestones 1 and 2
    # Step 5: Check milestone 3 chest is Claimed
    # Step 6: Validate expected rewards against magicbean_reward_table.json
    #

    try:
        log_info(f"Start: tc05_badge_and_reward_content (level {UNLOCK_LEVEL}, {MILESTONE_3_WINS} cheat wins)")

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

        log_info(f"Start: cheat-win {MILESTONE_3_WINS} levels to reach milestone 3 (no claims yet)")
        run_step("open cheat console", cheat.open_cheat)
        run_step(f"cheat magicbean progress +{MILESTONE_3_WINS}", cheat.cheat_magicbean_progress, wins=MILESTONE_3_WINS)
        run_step("close cheat console", cheat.close_cheat)
        log_info(f"End: cheat-win {MILESTONE_3_WINS} levels to reach milestone 3")

        assert run_step("open event popup", magic_bean.open_event_popup), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        sleep(10)  # Wait for large progress animation to finish

        log_info(f"Start: Check beanstalk progress visually reaches level {MILESTONE_3_WINS}")
        if not magic_bean.check_beanstalk_progress(MILESTONE_3_WINS):
            raise AssertionError(
                f"Result: Expected: beanstalk visually reaches level {MILESTONE_3_WINS} | Actual: check failed"
            )
        log_info(f"Result: Expected: beanstalk visually reaches level {MILESTONE_3_WINS} | Actual: reached")
        log_info(f"End: Check beanstalk progress visually reaches level {MILESTONE_3_WINS}")

        # Since verifying an unlocked chest now requires tapping and claiming it,
        # we cannot verify milestone 3 is unlocked *before* claiming milestones 1 and 2
        # without altering the claim order. So we just proceed to claim 1 and 2 first.
        
        for step_num, step_wins in [(1, MILESTONE_1_WINS), (2, MILESTONE_2_WINS)]:
            log_info(f"Start: Claim milestone {step_num} chest")
            magic_bean.tap_chest_at_level(step_wins)
            sleep(2)
            home_page.tap(home_page.tap_to_claim)
            sleep(5)
            sleep(2)
            log_info(f"Result: Expected: claim chest succeeds for milestone {step_num} | Actual: tapped")
            log_info(f"End: Claim milestone {step_num} chest")

        # milestone 3 (reached at 10 wins) should still be waiting to be claimed.
        # We verify it is unlocked (which will tap and claim it).
        log_info("Start: Check milestone 3 chest is Unlocked after claiming milestones 1 and 2")
        magic_bean.tap_chest_at_level(MILESTONE_3_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        # Milestone 3 contains multiple items which may require multiple taps to fully claim
        while home_page.wait_for_element(home_page.tap_to_claim, timeout=2):
            home_page.tap(home_page.tap_to_claim)
            sleep(3)
        sleep(2)
        log_info(
            "Result: Expected: milestone 3 chest Unlocked | Actual: tapped"
        )
        log_info("End: Check milestone 3 chest is Unlocked after claiming milestones 1 and 2")
        
        sleep(5)

        log_info("Start: Check milestone 3 chest is Claimed")
        if not magic_bean.is_chest_claimed(MILESTONE_3_WINS, timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 3 chest Claimed | Actual: not Claimed"
            )
        log_info("Result: Expected: milestone 3 chest Claimed | Actual: Claimed")
        log_info("End: Check milestone 3 chest is Claimed")

        # Data-consistency check only: compares expected constants against the
        # reward-table JSON. It does NOT read the screen -- an on-device
        # reward/display mismatch is not caught here.
        log_info("Start: Validate expected rewards against magicbean_reward_table.json")
        for milestone, expected_coins, expected_items in REWARD_CHECKS:
            log_info(f"Start: Validate milestone {milestone} rewards")
            
            ok, reason = magic_bean.validate_reward_against_db(
                milestone=milestone,
                expected_coins=expected_coins,
                expected_items=expected_items,
            )
            
            if not ok:
                raise AssertionError(
                    f"Result: Expected: milestone {milestone} rewards match DB "
                    f"(coins={expected_coins}, items={expected_items}) | "
                    f"Actual: Mismatch - {reason}"
                )
                
            log_info(
                f"Result: Expected: milestone {milestone} rewards match DB "
                f"(coins={expected_coins}, items={expected_items}) | "
                f"Actual: Matched successfully"
            )
            log_info(f"End: Validate milestone {milestone} rewards")
            
        log_info("End: Validate expected rewards against magicbean_reward_table.json")

        sleep(5)
        log_info("End: tc05_badge_and_reward_content")
    except Exception as e:
        wrapper.log_error(f"TC05_error: {str(e)}")
        snapshot(filename="tc05_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()

