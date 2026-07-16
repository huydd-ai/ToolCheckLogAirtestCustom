from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper

from pixon.pages.home_page import HomePage
from pixon.pages.lava_quest_page import LavaQuestPage

from pixon.common.test_flow import (
    run_step,
    teardown_app,
    stop_app_only,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import restore_system_time, clear_app_data, cold_start_with_json, set_time_relative, wait_for_app_ready

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc08_edg_clock_bypass")


        log_info("[Step 0] START: restore device clock to real time", snapshot=False)
        run_step("restore device clock to real time", restore_system_time)
        log_info("[Step 0] RESULT — expected: device clock synced to real time | actual: restore_system_time returned without error")
        log_info("[Step 0] END", snapshot=False)

        log_info("[Step 1] START: advance time, cold start at lv33, reach home", snapshot=False)
        run_step("advance time to expire old events", set_time_relative, 25.0)
        run_step("clear data", clear_app_data)
        run_step(
            "cold start at level 33",
            cold_start_with_json,
            {"level": 33, **LavaQuestPage.DEFAULT_PROFILE}
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after launch", close_all_popups, home_page)
        run_step("navigate home after launch", go_home_clean, home_page)
        home_reached = home_page.wait_for_element(home_page.btn_main_home, timeout=5)
        log_info(f"[Step 1] RESULT — expected: app launched at lv33 and home reached | actual: home_reached={bool(home_reached)}")
        log_info("[Step 1] END", snapshot=False)

        log_info("[Step 2] START: first-time flow setup (initialize quest)", snapshot=False)
        lava_quest.initialize_quest(home_page)
        log_info("[Step 2] RESULT — expected: first-time LQ flow completed | actual: initialize_quest returned without error")
        log_info("[Step 2] END", snapshot=False)

        log_info("[Step 3] START: exit, advance clock +6h, reopen, verify LQ popup opens", snapshot=False)
        stop_app_only()
        sleep(2)
        set_time_relative(6.0)
        run_step(
            "cold start at level 33 (no clear data)",
            cold_start_with_json,
            {"level": 33, **LavaQuestPage.DEFAULT_PROFILE, "clear_data": False}
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after +6h", close_all_popups, home_page)
        run_step("navigate home after +6h", go_home_clean, home_page)

        popup_opened = lava_quest.open_lava_quest_popup()
        log_info(f"[Step 3] RESULT — expected: LQ popup opens after +6h clock bypass | actual: popup_opened={bool(popup_opened)}")
        if not popup_opened:
            raise AssertionError("Lava Quest popup did not open after clock bypass")
        log_info("[Step 3] END", snapshot=False)

        sleep(3)
        log_info("End: tc08_edg_clock_bypass — all checks passed")
    except Exception as e:
        snapshot(filename="tc08_error.png")
        wrapper.log_error(f"TC08_error: {str(e)}")
    finally:
        teardown_app(__file__)

if __name__ == "__main__":
    main()
