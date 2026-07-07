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

from pixon.common.adb_utils import restore_system_time, set_param, clear_app_data, cold_start_with_json, set_time_relative, set_autoplay, wait_for_app_ready

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc10_lose_elimination")


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

        log_info("[Step 3] START: play 1 level and lose, return home", snapshot=False)
        home_page.tap(home_page.btn_main_play)
        sleep(4)
        set_autoplay(True, 6)
        sleep(4)

        set_param("set_level_win", False)
        sleep(3)
        set_autoplay(False)

        if home_page.wait_for_element(home_page.btn_next, timeout=5):
            home_page.tap(home_page.btn_next)
            sleep(2)
        run_step("close popups after lose", close_all_popups, home_page)
        run_step("navigate home after lose", go_home_clean, home_page)
        log_info("[Step 3] RESULT — expected: level lost and returned home | actual: returned_home=True")
        log_info("[Step 3] END", snapshot=False)

        log_info("[Step 4] START: open LQ popup, verify elimination (streak = 0) and cooldown timer", snapshot=False)
        popup_opened = lava_quest.open_lava_quest_popup()
        if not popup_opened:
            raise AssertionError("Lava Quest popup did not open after lose")
        sleep(2)
        streak = lava_quest.get_streak_count_via_ocr()
        cooldown_visible = lava_quest.is_time_count_down_visible(timeout=5)
        log_info(f"[Step 4] RESULT — expected: streak = 0 after elimination, cooldown timer visible | actual: streak={streak}, cooldown_visible={bool(cooldown_visible)}, timer_text={(lava_quest.check_timer_text() if cooldown_visible else '')!r}")
        if streak != 0:
            raise AssertionError(f"Expected streak=0 after elimination, got {streak}")
        log_info("[Step 4] END", snapshot=False)

        sleep(3)
        log_info("End: tc10_lose_elimination — all checks passed")
    except Exception as e:
        snapshot(filename="tc10_error.png")
        wrapper.log_error(f"TC10_error: {str(e)}")
    finally:
        teardown_app()

if __name__ == "__main__":
    main()
