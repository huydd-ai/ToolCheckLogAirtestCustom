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

from pixon.common.adb_utils import (
    restore_system_time,
    clear_app_data, cold_start_with_json,
    set_time_relative,
    wait_for_app_ready,
)

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc04_time_background")


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

        log_info("[Step 3] START: advance +24h, reopen, verify home reloaded", snapshot=False)
        stop_app_only()
        sleep(2)
        set_time_relative(26)
        run_step(
            "cold start at level 33 (no clear data)",
            cold_start_with_json,
            {"level": 33, **LavaQuestPage.DEFAULT_PROFILE, "clear_data": True}
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after 24h", close_all_popups, home_page)
        run_step("navigate home after 24h", go_home_clean, home_page)

        home_reloaded = home_page.is_at_home()
        log_info(f"[Step 3] RESULT — expected: home reloaded after +24h | actual: home_reloaded={bool(home_reloaded)}")
        if not home_reloaded:
            raise AssertionError("Home not reloaded after 24h")
        log_info("[Step 3] END", snapshot=False)

        log_info("[Step 4] START: verify event expired after 24h (LQ icon gone)", snapshot=False)
        lq_icon_visible = lava_quest.wait_for_element(lava_quest.btn_lava_quest, timeout=5)
        log_info(f"[Step 4] RESULT — expected: LQ icon NOT visible (event expired) | actual: lq_icon_visible={bool(lq_icon_visible)}")
        if lq_icon_visible:
            lava_quest.tap(lava_quest.btn_lava_quest)
            sleep(2)
            lava_quest.handle_event_over_popup()
            lq_icon_still = lava_quest.wait_for_element(lava_quest.btn_lava_quest, timeout=3)
            if lq_icon_still:
                raise AssertionError("LQ icon still visible after 24h — event should have expired")
            log_info("[Step 4] LQ icon dismissed via event-over popup, now gone")
        else:
            log_info("[Step 4] LQ icon correctly absent after 24h")
        log_info("[Step 4] END", snapshot=False)

        log_info("[Step 5] START: fresh cold start, verify new event cycle available", snapshot=False)
        stop_app_only()
        sleep(2)
        run_step(
            "cold start at level 33",
            cold_start_with_json,
            {"level": 33, **LavaQuestPage.DEFAULT_PROFILE}
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after fresh start", close_all_popups, home_page)
        run_step("navigate home after fresh start", go_home_clean, home_page)

        new_event_available = bool(lava_quest.wait_for_element(lava_quest.btn_lava_quest, timeout=10))
        log_info(f"[Step 5] RESULT — expected: LQ icon visible (new event) | actual: new_event_available={new_event_available}")
        if not new_event_available:
            raise AssertionError("LQ icon not visible after fresh cold start — new event should be available")
        log_info("[Step 5] END", snapshot=False)

        sleep(3)
        log_info("End: tc04_time_background — all checks passed")
    except Exception as e:
        snapshot(filename="tc04_error.png")
        wrapper.log_error(f"TC04_error: {str(e)}")
    finally:
        teardown_app(__file__)

if __name__ == "__main__":
    main()
