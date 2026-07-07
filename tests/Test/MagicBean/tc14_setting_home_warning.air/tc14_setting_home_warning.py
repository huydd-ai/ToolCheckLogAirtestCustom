from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.common.wrappers import log_info
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.pages.cheat_page import CheatPage
from pixon.pages.setting_page import SettingPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    wait_for_app_ready,
)

home_page = HomePage()
magic_bean = MagicBeanPage()
cheat = CheatPage()
setting = SettingPage()

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


def main():
    # TC14 -- Milestone in streak, enter a level, Setting -> Home:
    # warning popup appears; confirming exits to Home (streak reset).
    try:
        log_info("Start: tc14_setting_home_warning")
        boot()
        cheat_wins(MILESTONE_1_WINS)
        run_step("Go back homepage", go_home_clean, home_page)
        run_step("Close all popups", close_all_popups, home_page)

        run_step("enter level", home_page.tap, home_page.btn_main_play)
        sleep(5)

        log_info("Start: Setting -> Home, expect warning popup")
        if not setting.quit_to_home():
            raise AssertionError("Result: Expected: Setting panel with Home | Actual: not found")
        if not magic_bean.is_warning_popup_visible(timeout=8):
            raise AssertionError(
                "Result: Expected: progress-loss warning popup on Home quit | Actual: not shown"
            )
        log_info("Result: Expected: warning popup on Home quit | Actual: shown")

        log_info("Start: Confirm Home quit, expect landing at Home")
        magic_bean.tap(setting.btn_home_quit)
        sleep(12)  # inter ads + event popup lose anim

        run_step("Close all popups", close_all_popups, home_page)
        if not home_page.is_at_home():
            raise AssertionError(
                "Result: Expected: at Home after Home-quit confirm | Actual: not at Home"
            )
        log_info("Result: Expected: at Home after Home-quit confirm | Actual: at Home")

        log_info("End: tc14_setting_home_warning")
    except Exception as e:
        wrapper.log_error(f"TC14_error: {str(e)}")
        snapshot(filename="tc14_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
