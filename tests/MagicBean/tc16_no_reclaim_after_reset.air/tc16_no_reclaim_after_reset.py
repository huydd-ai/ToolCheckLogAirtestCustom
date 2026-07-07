from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
    set_autoplay,
    set_param,
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
MILESTONE_1_WINS = 2


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


def cheat_wins(n):
    run_step("open cheat console", cheat.open_cheat)
    run_step(f"cheat magicbean progress +{n}", cheat.cheat_magicbean_progress, wins=n)


def enter_level_and_lose():
    run_step("enter level", home_page.tap, home_page.btn_main_play)
    sleep(4)
    run_step("autoplay on", set_autoplay, True, 6)
    sleep(4)
    run_step("force level result = lose", set_param, "set_level_win", False)
    sleep(3)
    run_step("autoplay off", set_autoplay, False)


def main():
    # TC16 -- Claim milestone 1, lose (streak reset), win back to milestone 1
    # threshold: chest 1 must stay Claimed (tick), never Unlocked again.
    try:
        log_info("Start: tc16_no_reclaim_after_reset")
        boot()

        cheat_wins(MILESTONE_1_WINS)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)
        run_step("open event popup", magic_bean.open_event_popup)
        if not magic_bean.claim_chest():
            raise AssertionError("Result: Expected: claim milestone 1 | Actual: claim failed")
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        enter_level_and_lose()
        sleep(5)
        run_step("Close all popups after lose chain", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        cheat_wins(MILESTONE_1_WINS)  # re-reach milestone 1 threshold
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)
        run_step("open event popup", magic_bean.open_event_popup)
        sleep(1)

        log_info("Start: Check chest 1 stays Claimed (no re-claim)")
        if magic_bean.is_chest_unlocked(timeout=4):
            raise AssertionError(
                "Result: Expected: claimed milestone never re-unlocks | Actual: chest Unlocked again"
            )
        if not magic_bean.is_chest_claimed(timeout=10):
            raise AssertionError(
                "Result: Expected: chest 1 shows Claimed tick | Actual: tick missing"
            )
        log_info("Result: Expected: chest 1 stays Claimed after re-reaching | Actual: Claimed")

        log_info("End: tc16_no_reclaim_after_reset")
    except Exception as e:
        wrapper.log_error(f"TC16_error: {str(e)}")
        snapshot(filename="tc16_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
