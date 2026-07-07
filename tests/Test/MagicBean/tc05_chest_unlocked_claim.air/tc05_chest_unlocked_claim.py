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
    # TC05 -- Cold start above the unlock threshold, use the cheat console to
    # reach milestone 1 (2 cumulative wins) without real play, verify chest 1
    # becomes Unlocked, claim it, and verify it becomes Claimed with no
    # blocking confirmation popup.

    try:
        log_info(f"Start: tc05_chest_unlocked_claim (level {UNLOCK_LEVEL}, {MILESTONE_1_WINS} cheat wins)")

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

        log_info("Start: Check chest 1 is Unlocked after reaching milestone 1")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: chest 1 is Unlocked after 2 cumulative wins | Actual: chest 1 not Unlocked"
            )
        log_info(
            "Result: Expected: chest 1 is Unlocked after 2 cumulative wins | Actual: chest 1 Unlocked"
        )
        log_info("End: Check chest 1 is Unlocked after reaching milestone 1")

        # claim_chest() taps the chest, waits for the reward overlay, and taps
        # HomePage.tap_to_claim to collect it -- this assertion just confirms
        # the whole flow completes and reports success.
        log_info("Start: Check claim_chest completes without extra blocking popup")
        claimed_ok = magic_bean.claim_chest()
        if not claimed_ok:
            raise AssertionError(
                "Result: Expected: claim_chest() completes and returns True with no extra confirmation popup | "
                "Actual: claim_chest() returned False"
            )
        log_info(
            "Result: Expected: claim_chest() completes and returns True with no extra confirmation popup | Actual: True"
        )
        log_info("End: Check claim_chest completes without extra blocking popup")

        log_info("Start: Check chest 1 is Claimed after claim_chest()")
        if not magic_bean.is_chest_claimed(timeout=10):
            raise AssertionError(
                "Result: Expected: chest 1 is Claimed after claim_chest() | Actual: chest 1 not Claimed"
            )
        log_info("Result: Expected: chest 1 is Claimed after claim_chest() | Actual: chest 1 Claimed")
        log_info("End: Check chest 1 is Claimed after claim_chest()")

        sleep(5)
        log_info("End: tc05_chest_unlocked_claim")
    except Exception as e:
        wrapper.log_error(f"TC05_error: {str(e)}")
        snapshot(filename="tc05_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
