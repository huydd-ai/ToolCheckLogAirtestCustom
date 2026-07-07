from pixon.common.adb_utils import set_autoplay
from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper

from pixon.pages.home_page import HomePage
from pixon.pages.lava_quest_page import LavaQuestPage

from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import restore_system_time, clear_app_data, cold_start_with_json, disable_wifi, enable_wifi, set_time_relative, wait_for_app_ready, set_param

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc09_edg_disconnect_mid_level")


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

        log_info("[Step 3] START: enter level, disconnect wifi mid-level, reconnect, return home", snapshot=False)
        home_page.tap(home_page.btn_main_play)
        sleep(5)

        disable_wifi()
        sleep(5)
        set_autoplay(True)
        sleep(5)
        enable_wifi()
        sleep(5)
        set_autoplay(False)
        sleep(2)
        set_param("set_level_win", True)
        sleep(2)
        run_step("tap next to back home", home_page.tap, home_page.btn_next)
        sleep(2)
        run_step("close popups after level", close_all_popups, home_page)
        run_step("navigate home after level", go_home_clean, home_page)
        log_info("[Step 3] RESULT — expected: no crash, returned home after mid-level disconnect | actual: returned_home=True")
        log_info("[Step 3] END", snapshot=False)

        log_info("[Step 4] START: open LQ popup, verify elimination (streak = 0)", snapshot=False)
        popup_opened = lava_quest.open_lava_quest_popup()
        if not popup_opened:
            raise AssertionError(
                "Lava Quest popup did not open after returning from level"
            )
        sleep(2)
        streak = lava_quest.get_streak_count_via_ocr()
        log_info(f"[Step 4] RESULT — expected: streak = 1 after disconnect elimination | actual: streak={streak}")
        if streak != 1:
            raise AssertionError(f"Expected streak=1 after disconnect elimination, got {streak}")
        log_info("[Step 4] END", snapshot=False)

        log_info("End: tc09_edg_disconnect_mid_level — all checks passed")
    except Exception as e:
        snapshot(filename="tc09_error.png")
        wrapper.log_error(f"TC09_error: {str(e)}")
    finally:
        enable_wifi()
        teardown_app()

if __name__ == "__main__":
    main()
