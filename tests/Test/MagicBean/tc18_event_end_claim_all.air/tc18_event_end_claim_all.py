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
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
MILESTONE_1_WINS = 2
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
    # TC18 -- Unclaimed milestone at event end: reopening past duration expiry
    # shows no popup and no cue (Home looks unchanged, same as tc17) -- the
    # unclaimed chest is only visible by opening the event board, exactly
    # like during normal play. After claiming it, the icon still needs one
    # more level played before it disappears (same removal rule as tc19).
    try:
        log_info("Start: tc18_event_end_claim_all")
        run_step("restore device clock to real time", restore_system_time)
        boot()
        cheat_wins(MILESTONE_1_WINS)  # milestone 1 unlocked, NOT claimed
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        run_step("kill app before time jump", stop_app_only)
        run_step("advance clock past event duration", set_time_relative, EVENT_DURATION_HOURS + 1)
        run_step(
            "reopen app keeping data",
            cold_start_with_combined,
            clear_data=False,
            server_sync=True,
            fakeads=True,
            playspeed=6,
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

        log_info("Start: Check no popup/cue right after reopen, unclaimed chest reachable via event board")
        if not magic_bean.open_event_popup(timeout=10):
            raise AssertionError(
                "Result: Expected: event board opens same as during normal play | Actual: did not open"
            )
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: milestone 1 chest still Unlocked after expiry | Actual: not Unlocked"
            )
        log_info(
            "Result: Expected: event board opens with milestone 1 chest still Unlocked | Actual: as expected"
        )
        log_info("End: Check no popup/cue right after reopen, unclaimed chest reachable via event board")

        log_info("Start: Claim the chest via the normal chest -> overlay -> tap-to-claim flow")
        claimed_ok = magic_bean.claim_chest()
        if not claimed_ok:
            raise AssertionError("Result: Expected: claim_chest() succeeds post-expiry | Actual: returned False")
        log_info("Result: Expected: claim_chest() succeeds post-expiry | Actual: True")
        log_info("End: Claim the chest via the normal chest -> overlay -> tap-to-claim flow")

        run_step("Close all popups", close_all_popups, home_page)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Check icon still visible before playing another level (removal needs 1 more level)")
        if not magic_bean.is_event_icon_visible(timeout=10):
            raise AssertionError(
                "Result: Expected: icon still visible right after claiming (removal requires 1 more level, "
                "see tc19) | Actual: icon already gone"
            )
        log_info(
            "Result: Expected: icon still visible right after claiming | Actual: visible"
        )
        log_info("End: Check icon still visible before playing another level (removal needs 1 more level)")

        log_info("Start: Play one more level, expect icon removed on return (same rule as tc19)")
        run_step("open cheat console", cheat.open_cheat)
        run_step("cheat win one level", cheat.win_level_and_continue)
        sleep(2)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        if magic_bean.is_event_icon_visible(timeout=5):
            raise AssertionError(
                "Result: Expected: event icon removed after 1 level post-claim-at-end | Actual: icon still visible"
            )
        log_info("Result: Expected: event icon removed after 1 level post-claim-at-end | Actual: removed")
        log_info("End: Play one more level, expect icon removed on return (same rule as tc19)")

        log_info("End: tc18_event_end_claim_all")
    except Exception as e:
        wrapper.log_error(f"TC18_error: {str(e)}")
        snapshot(filename="tc18_error.png")
    finally:
        restore_system_time()
        teardown_app()


if __name__ == "__main__":
    main()
