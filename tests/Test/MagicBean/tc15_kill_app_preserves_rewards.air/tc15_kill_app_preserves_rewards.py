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


def wait_home():
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


def cheat_wins(n):
    run_step("open cheat console", cheat.open_cheat)
    run_step(f"cheat magicbean progress +{n}", cheat.cheat_magicbean_progress, wins=n)


def main():
    # TC15 -- Claim milestone 1, unlock milestone 2 (unclaimed), kill app
    # mid-level, reopen keeping data: claimed tick preserved, unclaimed chest
    # still Unlocked. No unclaimed-reward indicator exists on real device;
    # chest state is the only checkable signal.
    try:
        log_info("Start: tc15_kill_app_preserves_rewards")
        boot()

        cheat_wins(MILESTONE_1_WINS)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)
        run_step("open event popup", magic_bean.open_event_popup)
        if not magic_bean.claim_chest():
            raise AssertionError("Result: Expected: claim milestone 1 | Actual: claim failed")
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        cheat_wins(MILESTONE_2_WINS)  # milestone 2 unlocked, unclaimed
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        run_step("enter level", home_page.tap, home_page.btn_main_play)
        sleep(5)
        run_step("kill app mid-level", stop_app_only)
        sleep(3)

        # reopen WITHOUT wiping data (project rule: reopen = clear_data=False,
        # server_sync=True)
        run_step(
            "reopen app keeping data",
            cold_start_with_combined,
            clear_data=False,
            server_sync=True,
            fakeads=True,
            playspeed=6,
        )
        sleep(15)
        wait_home()

        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info("Start: Check claimed tick preserved")
        if not magic_bean.is_chest_claimed(timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 1 tick preserved | Actual: tick missing"
            )
        log_info("Result: Expected: milestone 1 tick preserved | Actual: preserved")

        log_info("Start: Check unclaimed chest still Unlocked")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 2 chest still Unlocked | Actual: not Unlocked"
            )
        log_info("Result: Expected: milestone 2 chest still Unlocked | Actual: Unlocked")

        log_info("End: tc15_kill_app_preserves_rewards")
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
