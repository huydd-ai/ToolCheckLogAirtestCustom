from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
)


home_page = HomePage()
magic_bean = MagicBeanPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL


def main():
    # TC04 -- Cold start above the unlock threshold with 0 event wins. Open the
    # event popup, verify chest 1 is Locked, tap it and verify nothing happens
    # (no tooltip, no popup -- a Locked chest is a dead tap on real device).

    try:
        log_info(f"Start: tc04_chest_locked (level {UNLOCK_LEVEL}, 0 wins)")

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

        # capture-time TODO: verify whether the event icon/popup is present with
        # 0 wins at lv>=UNLOCK_LEVEL (unlock may be gated on "won a level while
        # >= threshold" rather than a plain level poll -- see tc01's analogous
        # note). If open_event_popup() returns False here, the icon may need an
        # extra win to appear; re-check once a real build is available.
        log_info("Start: Check event popup opens with 0 wins above threshold")
        if not magic_bean.open_event_popup(timeout=10):
            raise AssertionError(
                f"Result: Expected: Magic Bean event popup opens at lv{UNLOCK_LEVEL} with 0 wins | "
                f"Actual: popup/board did not appear"
            )
        log_info(
            f"Result: Expected: Magic Bean event popup opens at lv{UNLOCK_LEVEL} with 0 wins | Actual: popup/board appeared"
        )
        log_info("End: Check event popup opens with 0 wins above threshold")

        log_info("Start: Check chest 1 is Locked with 0 wins")
        if not magic_bean.is_chest_locked(timeout=5):
            raise AssertionError(
                "Result: Expected: chest 1 is Locked with 0 wins | Actual: chest 1 not Locked"
            )
        log_info("Result: Expected: chest 1 is Locked with 0 wins | Actual: chest 1 Locked")
        log_info("End: Check chest 1 is Locked with 0 wins")

        run_step("tap locked chest", magic_bean.tap, magic_bean.chest_locked)
        sleep(1)

        log_info("Start: Check nothing happens when tapping a Locked chest")
        if not magic_bean.is_chest_locked(timeout=5):
            raise AssertionError(
                "Result: Expected: chest 1 remains Locked, no popup/state change from tapping it | "
                "Actual: chest 1 no longer Locked"
            )
        log_info(
            "Result: Expected: chest 1 remains Locked, no popup/state change from tapping it | "
            "Actual: chest 1 still Locked"
        )
        log_info("End: Check nothing happens when tapping a Locked chest")

        sleep(5)
        log_info("End: tc04_chest_locked")
    except Exception as e:
        wrapper.log_error(f"TC04_error: {str(e)}")
        snapshot(filename="tc04_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
