from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app, stop_app_only
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
    set_time_relative,
    restore_system_time,
)

home_page = HomePage()
magic_bean = MagicBeanPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
EVENT_DURATION_HOURS = 168.0  # remote config default


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


def main():
    # TC17 -- With event active (nothing unclaimed), jump the device clock
    # past the 168h duration and reopen: there is no popup and no persistent
    # label on real device -- Home looks completely unchanged. The icon must
    # still be visible right after this reopen; it only gets removed after
    # the player finishes one more level (verified separately by tc19).
    try:
        log_info("Start: tc17_event_end_finished")
        run_step("restore device clock to real time", restore_system_time)
        boot()

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

        log_info("Start: Check icon still visible immediately after reopen past expiry (no cue, no popup)")
        if not magic_bean.is_event_icon_visible(timeout=15):
            raise AssertionError(
                "Result: Expected: icon still visible right after reopen past duration expiry "
                "(removal requires 1 more level, see tc19) | Actual: icon already gone"
            )
        log_info(
            "Result: Expected: icon still visible right after reopen past duration expiry | Actual: visible"
        )

        log_info("End: tc17_event_end_finished")
    except Exception as e:
        wrapper.log_error(f"TC17_error: {str(e)}")
        snapshot(filename="tc17_error.png")
    finally:
        restore_system_time()
        teardown_app()


if __name__ == "__main__":
    main()
