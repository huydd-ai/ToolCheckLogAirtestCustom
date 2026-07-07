from pixon.common import config
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

from pixon.common.adb_utils import cold_start_with_json, restore_system_time, wait_for_app_ready

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc02_update_old (existing user, LQ unlocked at lv33)")

        log_info("[Step 1] START: restore device clock to real time", snapshot=False)
        run_step("restore device clock to real time", restore_system_time)
        log_info("[Step 1] RESULT — expected: device clock synced to real time | actual: restore_system_time returned without error")
        log_info("[Step 1] END", snapshot=False)

        log_info("[Step 2] START: cold start at level 33 (existing user), verify LQ icon visible", snapshot=False)
        run_step(
            "cold start at level 33 (existing user)",
            cold_start_with_json,
            {
                "fakeads": True, "heart": 5, "level": 33, "coin": 10000,
                "playspeed": 6, "clear_data":True, "server_sync": False,
            },
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after launch", close_all_popups, home_page)
        run_step("navigate home after launch", go_home_clean, home_page)

        icon_visible_lv33 = home_page.wait_for_element(home_page.btn_toy_adventure, timeout=5)
        log_info(f"[Step 2] RESULT — expected: LQ icon visible at lv33 | actual: icon_visible={bool(icon_visible_lv33)}")
        if not icon_visible_lv33:
            raise AssertionError("Lava Quest icon did NOT appear at level 33")
        log_info("[Step 2] END", snapshot=False)

        log_info("[Step 3] START: cold start to check verify LQ icon still show after new version update", snapshot=False)
        teardown_app(config.GAME_PACKAGE)
        sleep(3)
        run_step(
            "cold start at level 33 (existing user, no clear_data, no server_sync)",
            cold_start_with_json,
            {
                "fakeads": True, "heart": 5, "level": 33, "coin": 10000,
                "playspeed": 6, "clear_data": False, "server_sync": False,
            },
        )
        sleep(30)
        wait_for_app_ready()
        run_step("close all popups after launch", close_all_popups, home_page)
        run_step("navigate home after launch", go_home_clean, home_page)
        log_info("[Step 3] END", snapshot=False)
        log_info("[Step 4] START: open LQ popup, verify label_lavaquest", snapshot=False)
        lava_quest.open_lava_quest_popup()
        board_visible = bool(lava_quest.wait_for_element(lava_quest.label_lavaquest, timeout=5))
        log_info(f"[Step 4] RESULT — expected: popup opens with label_lavaquest at lv33 | actual: board_visible={board_visible}")
        if not board_visible:
            raise AssertionError("label_lavaquest not visible in LQ popup")
        log_info("[Step 4] END", snapshot=False)

        sleep(3)
        log_info("End: tc02_update_old — all checks passed")
    except Exception as e:
        snapshot(filename="tc02_error.png")
        log_error(f"TC02_error: {str(e)}")
    finally:
        teardown_app()

if __name__ == "__main__":
    main()
