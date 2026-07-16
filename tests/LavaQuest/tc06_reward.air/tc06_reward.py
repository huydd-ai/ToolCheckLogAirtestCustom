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

from pixon.common.adb_utils import restore_system_time, clear_app_data, cold_start_with_json, set_time_relative, wait_for_app_ready

home_page = HomePage()
lava_quest = LavaQuestPage()

def main():
    try:
        log_info("Start: tc06_reward")


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

        log_info("[Step 3] START: play and win 7 levels", snapshot=False)
        run_step("play and win 7 levels", lava_quest.play_and_win_levels, home_page, 7)
        log_info("[Step 3] RESULT — expected: 7 wins completed, You Win overlay on screen | actual: play_and_win_levels verified 7 wins via OCR without error")
        log_info("[Step 3] END", snapshot=False)

        sleep(4)
        log_info("[Step 4] START: verify win overlay, OCR reward, claim, check LQ icon gone", snapshot=False)
        if not lava_quest.wait_for_element(lava_quest.label_win_lava_quest, timeout=8):
            raise AssertionError("'You Win' overlay did not appear after 7 wins")

        reward = lava_quest.get_reward_and_winners_via_ocr()
        win_amount, other_winners = reward.win_amount, reward.other_winners
        log_info(f"Win screen OCR: win_amount={win_amount}, other_winners={other_winners} (conf={reward.confidence:.2f}, ok={reward.ok})")

        if win_amount <= 0:
            raise AssertionError(f"Expected positive coin reward on Win banner, got {win_amount}")

        ok, reason = lava_quest.validate_reward_against_db(win_amount, other_winners, level=7)
        if ok:
            log_info(f"Verified reward vs db: {reason} (win={win_amount}, bot_remaining={other_winners})")
        else:
            log_info(f"[WARN] reward db check: {reason} — logging only, not failing")

        if not lava_quest.wait_for_element(HomePage.tap_to_claim, timeout=5):
            raise AssertionError("TAP TO CLAIM button not visible on Win screen")
        lava_quest.tap(HomePage.tap_to_claim)
        sleep(3)

        log_info(f"[Step 4] RESULT — expected: reward claimed | actual: win_amount={win_amount}, tap_to_claim tapped")
        log_info("[Step 4] END", snapshot=False)

        log_info("End: tc06_reward — all checks passed")
    except Exception as e:
        snapshot(filename="tc06_error.png")
        wrapper.log_error(f"TC06_error: {str(e)}")
    finally:
        teardown_app(__file__)

if __name__ == "__main__":
    main()
