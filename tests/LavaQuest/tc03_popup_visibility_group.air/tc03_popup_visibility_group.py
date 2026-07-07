from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper

from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import (
    restore_system_time,
    clear_app_data, cold_start_with_json,
    set_time_relative,
    wait_for_app_ready,
)

from pixon.pages.home_page import HomePage
from pixon.pages.lava_quest_page import LavaQuestPage

home_page = HomePage()
lava_quest = LavaQuestPage()

def run_e2e_flow():
    log_info("LV_E2E — End-to-end Lava Quest unlock and play flow")

    log_info("[Step 3] START: check Lava Quest icon on home screen", snapshot=False)
    icon_visible = lava_quest.wait_for_element(lava_quest.btn_lava_quest, timeout=10)
    log_info(f"[Step 3] RESULT — expected: LQ icon visible on home | actual: icon_visible={bool(icon_visible)}")
    if not icon_visible:
        raise AssertionError("Lava Quest icon did NOT appear on fresh install")
    log_info("[Step 3] END", snapshot=False)

    log_info("[Step 4] START: tap icon, check label_lavaquest popup header", snapshot=False)
    lava_quest.tap(lava_quest.btn_lava_quest)
    header_visible = lava_quest.wait_for_element(lava_quest.label_lavaquest, timeout=15)
    log_info(f"[Step 4] RESULT — expected: LQ popup header visible | actual: header_visible={bool(header_visible)}")
    if not header_visible:
        raise AssertionError("Lava Quest popup header did not appear")
    log_info("[Step 4] END", snapshot=False)

    log_info("[Step 5] START: tap btn_start", snapshot=False)
    run_step("tap btn_start", lava_quest.tap_btn_start)
    log_info("[Step 5] RESULT — expected: btn_start tapped to begin matchmaking | actual: tap_btn_start returned without error")
    log_info("[Step 5] END", snapshot=False)

    log_info("[Step 6] START: wait for matchmaking player group label", snapshot=False)
    sleep(3)
    group_visible = lava_quest.wait_for_element(lava_quest.label_player_group_lavaquest, timeout=10)
    log_info(f"[Step 6] RESULT — expected: matchmaking player group visible | actual: group_visible={bool(group_visible)}")
    if not group_visible:
        raise AssertionError("Matchmaking player group did not appear")
    log_info("[Step 6] END", snapshot=False)

    log_info("[Step 7] START: tap tap_to_continue", snapshot=False)
    sleep(2)
    continue_visible = lava_quest.wait_for_element(lava_quest.tap_to_continue, timeout=5)
    if continue_visible:
        lava_quest.tap(lava_quest.tap_to_continue)
    log_info(f"[Step 7] RESULT — expected: tap_to_continue dismissed if shown | actual: continue_shown={bool(continue_visible)}")
    log_info("[Step 7] END", snapshot=False)

    log_info("[Step 8] START: tap center screen 3 times to advance", snapshot=False)
    sleep(1)
    for _ in range(3):
        touch((360, 640))
        sleep(1)
    log_info("[Step 8] RESULT — expected: 3 center taps issued to advance flow | actual: 3 taps issued without error")
    log_info("[Step 8] END", snapshot=False)

    log_info("[Step 9] START: check level_complete and player_group labels", snapshot=False)
    level_complete_visible = lava_quest.wait_for_element(lava_quest.label_level_complete_lavaquest, timeout=5)
    players_count_visible = lava_quest.wait_for_element(lava_quest.label_players_number_count_lavaquest, timeout=5)
    log_info(f"[Step 9] RESULT — expected: level_complete (0/7) and players_count (100/100) visible | actual: level_complete={bool(level_complete_visible)}, players_count={bool(players_count_visible)}")
    if not level_complete_visible:
        raise AssertionError("Level complete (0/7) label not visible")
    if not players_count_visible:
        raise AssertionError("Player count (100/100) label not visible")
    log_info("[Step 9] END", snapshot=False)

    log_info("[Step 10] START: tap btn_close", snapshot=False)
    home_page.tap(home_page.btn_close)
    sleep(2)
    log_info("[Step 10] RESULT — expected: LQ popup closed | actual: btn_close tapped without error")
    log_info("[Step 10] END", snapshot=False)

    log_info("[Step 11] START: play and win 7 levels, check streak each win", snapshot=False)
    run_step(
        "play and win 7 levels",
        lava_quest.play_and_win_levels,
        home_page,
        7,
    )
    log_info("[Step 11] RESULT — expected: streak increments across all 7 wins | actual: play_and_win_levels verified 7 wins via OCR without error")
    log_info("[Step 11] END", snapshot=False)

def main():
    try:
        log_info("Start: TC03_E2E_FLOW")


        log_info("[Step 0] START: restore device clock to real time", snapshot=False)
        run_step("restore device clock to real time", restore_system_time)
        log_info("[Step 0] RESULT — expected: device clock synced to real time | actual: restore_system_time returned without error")
        log_info("[Step 0] END", snapshot=False)

        log_info("[Step 1] START: advance time to expire old events", snapshot=False)
        run_step("advance time to expire old events", set_time_relative, 25.0)
        log_info("[Step 1] RESULT — expected: device time advanced 25h | actual: set_time_relative returned without error")
        log_info("[Step 1] END", snapshot=False)

        log_info("[Step 2] START: cold start at lv33, navigate home", snapshot=False)
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
        log_info(f"[Step 2] RESULT — expected: app launched at lv33 and home reached | actual: home_reached={bool(home_reached)}")
        log_info("[Step 2] END", snapshot=False)

        run_e2e_flow()

        sleep(3)
        log_info("End: TC03_E2E_FLOW — passed")
    except Exception as e:
        snapshot(filename="tc03_error.png")
        wrapper.log_error(f"TC03_error: {str(e)}")
    finally:
        teardown_app()

if __name__ == "__main__":
    main()
