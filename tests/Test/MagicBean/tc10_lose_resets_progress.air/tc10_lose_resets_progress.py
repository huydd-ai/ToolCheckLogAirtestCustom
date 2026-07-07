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
    for i in range(n):
        run_step(f"open cheat console (win {i + 1}/{n})", cheat.open_cheat)
        run_step(f"cheat win level {i + 1}/{n}", cheat.win_level_and_continue)
        sleep(1)


def enter_level_and_lose():
    run_step("enter level", home_page.tap, home_page.btn_main_play)
    sleep(4)
    run_step("autoplay on", set_autoplay, True, 6)
    sleep(4)
    run_step("force level result = lose", set_param, "set_level_win", False)
    sleep(3)
    run_step("autoplay off", set_autoplay, False)


def main():
    # TC10 -- Streak >0 with an unclaimed milestone, lose a level: verify the
    # 3-popup lose chain shows in order (Close path each time), and after the
    # reset the unclaimed chest is still Unlocked.
    try:
        log_info("Start: tc10_lose_resets_progress")
        boot()
        cheat_wins(MILESTONE_1_WINS)  # milestone 1 unlocked, NOT claimed
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        enter_level_and_lose()

        log_info("Start: Check lose popup 1 appears")
        if not magic_bean.wait_for_element(magic_bean.lose_popup_1, timeout=15):
            raise AssertionError("Result: Expected: lose popup 1 visible | Actual: not found")
        log_info("Result: Expected: lose popup 1 visible | Actual: visible")
        magic_bean.tap(magic_bean.btn_close)
        sleep(2)

        log_info("Start: Check lose popup 2 (progress-loss warning + event list)")
        if not magic_bean.wait_for_element(magic_bean.lose_popup_2, timeout=10):
            raise AssertionError("Result: Expected: lose popup 2 visible | Actual: not found")
        log_info("Result: Expected: lose popup 2 visible | Actual: visible")
        magic_bean.tap(magic_bean.btn_close)
        sleep(2)

        log_info("Start: Check lose popup 3 (Try Again / lost heart)")
        if not magic_bean.wait_for_element(magic_bean.lose_popup_3, timeout=10):
            raise AssertionError("Result: Expected: lose popup 3 visible | Actual: not found")
        log_info("Result: Expected: lose popup 3 visible | Actual: visible")
        magic_bean.tap(magic_bean.btn_close)
        sleep(8)  # fakeads inter + lose animation on event popup

        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        log_info("Start: Check unclaimed milestone survives streak reset")
        if not magic_bean.open_event_popup():
            raise AssertionError("Result: Expected: event popup opens | Actual: open failed")
        if not magic_bean.is_chest_unlocked(timeout=10):
            raise AssertionError(
                "Result: Expected: chest 1 still Unlocked after lose reset | Actual: not Unlocked"
            )
        log_info("Result: Expected: chest 1 still Unlocked after lose reset | Actual: Unlocked")

        log_info("Start: Check beanstalk progress visually reset (no longer at milestone 1 level)")
        # Negative check: require a MEASURED not-reached (False). None means the
        # marker was not even found (OCR miss) -- failing loud instead of
        # false-passing the reset.
        progress_state = magic_bean.check_beanstalk_progress(MILESTONE_1_WINS)
        if progress_state is not False:
            raise AssertionError(
                f"Result: Expected: beanstalk reset below level {MILESTONE_1_WINS} after lose | "
                f"Actual: {'still shows reached' if progress_state else 'marker not measurable (OCR miss)'}"
            )
        log_info(
            f"Result: Expected: beanstalk reset below level {MILESTONE_1_WINS} after lose | Actual: reset"
        )
        log_info("End: Check beanstalk progress visually reset")

        log_info("End: tc10_lose_resets_progress")
    except Exception as e:
        wrapper.log_error(f"TC10_error: {str(e)}")
        snapshot(filename="tc10_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
