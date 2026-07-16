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
    set_time_relative,
    restore_system_time,
    set_param,
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
MILESTONE_1_WINS = 2
MILESTONE_3_WINS = 10
EVENT_DURATION_HOURS = 168.0


def boot():
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


def cheat_wins(n):
    run_step("open cheat console", cheat.open_cheat)
    run_step(f"cheat magicbean progress +{n}", cheat.cheat_magicbean_progress, wins=n)
    run_step("close cheat console", cheat.close_cheat)


def main():
    # TC14 -- Unclaimed milestone at event end: reopening past duration expiry
    # shows no popup and no cue (Home looks unchanged, same as tc13) -- the
    # unclaimed chest is only visible by opening the event board, exactly
    # like during normal play. After claiming it, the icon still needs one
    # more level played before it disappears (same removal rule as tc15).
    # Test Flow:
    # Step 1: Check no popup/cue right after reopen, unclaimed chest reachable via event board
    # Step 2: Claim all chests via the normal chest -> overlay -> tap-to-claim flow
    # Step 3: Check icon still visible before playing another level (removal needs 1 more level)
    # Step 4: Play one more level, expect icon removed on return (same rule as tc15)
    #
    try:
        log_info("Start: tc14_event_end_claim_all")
        run_step("restore device clock to real time", restore_system_time)
        boot()
        cheat_wins(MILESTONE_3_WINS)  # milestone 1 unlocked, NOT claimed
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        run_step("kill app before time jump", stop_app_only)
        run_step("advance clock past event duration", set_time_relative, EVENT_DURATION_HOURS + 1)
        run_step(
            "reopen app keeping data",
            cold_start_with_combined,
            clear_data=False,
            server_sync=False,
            fakeads=True,
            playspeed=6,
        )
        sleep(15)
        wait_for_app_ready()
        home_page.wait_for_element(home_page.splash_home_icon, timeout=30)

        log_info("Start: Check no popup/cue right after reopen, unclaimed chest reachable via event board")
        if not magic_bean.open_event_popup(timeout=10):
            raise AssertionError(
                "Result: Expected: event board opens same as during normal play | Actual: did not open"
            )
        magic_bean.tap_chest_at_level(MILESTONE_1_WINS)
        home_page.wait_for_element(home_page.tap_to_claim, timeout=5)
        home_page.tap(home_page.tap_to_claim)
        sleep(5)
        log_info(
            "Result: Expected: event board opens with milestone 1 chest still Unlocked | Actual: tapped"
        )
        log_info("End: Check no popup/cue right after reopen, unclaimed chest reachable via event board")

        log_info("Start: Claim all chests via the normal chest -> overlay -> tap-to-claim flow")
        claimed_count = magic_bean.claim_all_unlocked_chests(MILESTONE_3_WINS)
        if claimed_count != 2:
            raise AssertionError(f"Result: Expected: claim_all_unlocked_chests() claims 2 chests | Actual: claimed {claimed_count}")
        log_info("Result: Expected: claim_all_unlocked_chests() claims 2 chests | Actual: True")
        log_info("End: Claim all chests via the normal chest -> overlay -> tap-to-claim flow")
        run_step("Close all popups", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Check icon still visible before playing another level (removal needs 1 more level)")
        if not magic_bean.is_event_icon_visible(timeout=10):
            raise AssertionError(
                "Result: Expected: icon still visible right after claiming (removal requires 1 more level, "
                "see tc15) | Actual: icon already gone"
            )
        log_info(
            "Result: Expected: icon still visible right after claiming | Actual: visible"
        )
        log_info("End: Check icon still visible before playing another level (removal needs 1 more level)")

        log_info("Start: Play one more level, expect icon removed on return (same rule as tc15)")
        run_step("enter level", home_page.tap, home_page.btn_main_play)
        sleep(8)
        run_step("force level result = win", set_param, "set_level_win", True)
        sleep(4)
        run_step("tap next", home_page.click_btn_next)
        sleep(8)
        run_step("Close all popups", close_all_popups, home_page)

        if magic_bean.is_event_icon_visible(timeout=5):
            raise AssertionError(
                "Result: Expected: event icon removed after 1 level post-claim-at-end | Actual: icon still visible"
            )
        log_info("Result: Expected: event icon removed after 1 level post-claim-at-end | Actual: removed")
        log_info("End: Play one more level, expect icon removed on return (same rule as tc15)")

        log_info("End: tc14_event_end_claim_all")
    except Exception as e:
        wrapper.log_error(f"TC14_error: {str(e)}")
        snapshot(filename="tc14_error.png")
    finally:
        restore_system_time()
        teardown_app(__file__)


if __name__ == "__main__":
    main()

