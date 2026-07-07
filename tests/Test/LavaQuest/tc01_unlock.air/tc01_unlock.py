from pixon.common.wrappers import log_info, log_error

from airtest.core.api import *

from pixon.pages.home_page import HomePage
from pixon.pages.lava_quest_page import LavaQuestPage

from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import restore_system_time, clear_app_data, cold_start_with_json, set_time_relative, wait_for_app_ready

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc01_unlock (full LQ first-time flow at lv33)")


        log_info("[Step 0] START: restore device clock to real time", snapshot=False)
        run_step("restore device clock to real time", restore_system_time)
        log_info("[Step 0] RESULT — expected: device clock synced to real time | actual: restore_system_time returned without error")
        log_info("[Step 0] END", snapshot=False)

        log_info("[Step 1] START: advance time to expire old events", snapshot=False)
        run_step("advance time to expire old events", set_time_relative, 25.0)
        log_info("[Step 1] RESULT — expected: device time advanced 25h | actual: set_time_relative returned without error")
        log_info("[Step 1] END", snapshot=False)

        log_info("[Step 2] START: cold start at level 33, verify LQ icon visible", snapshot=False)
        run_step("clear data", clear_app_data)
        run_step(
            "cold start at level 33",
            cold_start_with_json,
            {"level": 33, **LavaQuestPage.DEFAULT_PROFILE}
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups lv33", close_all_popups, home_page)
        run_step("go home clean lv33", go_home_clean, home_page)

        icon_visible_lv33 = home_page.wait_for_element(home_page.btn_toy_adventure, timeout=5)
        log_info(f"[Step 2] RESULT — expected: LQ icon visible at lv33 | actual: icon_visible={bool(icon_visible_lv33)}")
        if not icon_visible_lv33:
            raise AssertionError("Lava Quest icon NOT visible at level 33")
        log_info("[Step 2] END", snapshot=False)

        log_info("End: tc01_unlock — all checks passed")
    except Exception as e:
        snapshot(filename="tc01_error.png")
        log_error(f"TC01_error: {str(e)}")
    finally:
        teardown_app()

if __name__ == "__main__":
    main()
