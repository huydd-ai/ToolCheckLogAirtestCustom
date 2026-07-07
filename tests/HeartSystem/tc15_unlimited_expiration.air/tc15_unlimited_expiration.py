from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
    stop_app,
)
from pixon.common.adb_utils import cold_start_with_combined, set_combined, set_param, set_time_relative
from pixon.common import config

home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()

def lose_level(home) -> None:
    run_step("trigger lose outcome", set_param, "set_level_win", False)
    sleep(1.5)
    for attempt in range(10):
        wrapper.log_info(f"lose_level: tapping btn_close (attempt {attempt + 1})")
        home.close_popup()
        sleep(0.75)
        if home.is_at_home():
            break

def variant_expires_mid_level():
    # TC38 EDG-05 — Unlimited expires mid-level: no deduction during, deduction after expiry
    log_info("Start: setup unlimited heart (heart=3, level=12, coin=5000)")
    run_step(
        "cold start with unlimited heart",
        cold_start_with_combined,
        fakeads=True,
        heart="unlimited",
        level=12,
        coin=5000,
        playspeed=config.GAME_START_PLAY_SPEED,
        server_sync=False,
    )
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: setup unlimited heart")

    log_info("Start: verify no heart deducted during unlimited window")
    count_before = heart_page.get_heart_count_via_ocr()

    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after lose", go_home_clean, home_page)
    count_after_win = heart_page.get_heart_count_via_ocr()
    if count_after_win != count_before:
        raise AssertionError(
            f"Heart deducted during unlimited window (before={count_before})"
        )
    else:
        log_info(f"Result: Expected count_after_win={count_before} | Actual count_after_win={count_after_win}")
    log_info("End: verify no heart deducted during unlimited window")

    log_info("Start: expire unlimited and verify deduction after expiry")
    run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
    run_step("advance clock by 1.1 hours", set_time_relative, 1.1)
    run_step(
        "cold start without heart reset",
        cold_start_with_combined,
        fakeads=True,
        playspeed=config.GAME_START_PLAY_SPEED,
        clear_data=False,
        server_sync=False,
    )
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)

    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after expiry lose", go_home_clean, home_page)
    count_after_expiry = heart_page.get_heart_count_via_ocr()
    if count_after_expiry == -1 or count_after_expiry >= 5:
        raise AssertionError(
            f"Heart NOT deducted after unlimited expired: after={count_after_expiry}"
        )
    else:
        log_info(f"Result: Expected count_after_expiry < 5 | Actual count_after_expiry={count_after_expiry}")
    log_info("End: expire unlimited and verify deduction after expiry")

def variant_simultaneous_claims():
    # TC39 EDG-06 — Two overlapping unlimited claims stack
    log_info("Start: setup unlimited heart (heart=3, level=12, coin=5000)")
    run_step(
        "cold start with unlimited heart",
        cold_start_with_combined,
        fakeads=True,
        heart="unlimited",
        level=12,
        coin=5000,
        playspeed=config.GAME_START_PLAY_SPEED,
        server_sync=False,
    )
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: setup unlimited heart")

    log_info("Start: verify first unlimited active and no deduction on lose")
    if not heart_page.is_unlimited_hearts_active():
        wrapper.log_info(
            "Unlimited badge not visible after first claim - proceeding"
        )
    count_before = heart_page.get_heart_count_via_ocr()

    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after first lose", go_home_clean, home_page)
    count_after_first = heart_page.get_heart_count_via_ocr()
    if count_after_first != count_before:
        raise AssertionError(
            f"Heart deducted during first unlimited (before={count_before})"
        )
    else:
        log_info(f"Result: Expected count_after_first={count_before} | Actual count_after_first={count_after_first}")
    log_info("End: verify first unlimited active and no deduction on lose")

    log_info("Start: add second unlimited claim and advance past first expiry")
    run_step("set combined second unlimited heart", set_combined, heart="unlimited")
    sleep(2)
    run_step("navigate to home after second grant", go_home_clean, home_page)
    count_mid = heart_page.get_heart_count_via_ocr()

    run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
    run_step("advance clock by 1.1 hours", set_time_relative, 1.1)
    run_step(
        "cold start without heart reset",
        cold_start_with_combined,
        fakeads=True,
        playspeed=config.GAME_START_PLAY_SPEED,
        clear_data=False,
        server_sync=False,
    )
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after mid lose", go_home_clean, home_page)
    count_after_mid = heart_page.get_heart_count_via_ocr()
    if count_after_mid != count_mid:
        raise AssertionError(
            f"Heart deducted after only first unlimited expired (mid={count_mid})"
        )
    else:
        log_info(f"Result: Expected count_after_mid={count_mid} | Actual count_after_mid={count_after_mid}")
    log_info("End: add second unlimited claim and advance past first expiry")

    log_info("Start: advance past second expiry and verify deduction")
    run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
    run_step("advance clock by 1.1 hours", set_time_relative, 1.1)
    run_step(
        "cold start without heart reset",
        cold_start_with_combined,
        fakeads=True,
        playspeed=config.GAME_START_PLAY_SPEED,
        clear_data=False,
        server_sync=False,
    )
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after both expired", go_home_clean, home_page)
    count_after_both = heart_page.get_heart_count_via_ocr()
    if count_after_both == -1 or count_after_both >= 5:
        raise AssertionError(
            f"Heart NOT deducted after both unlimited expired: after={count_after_both}"
        )
    else:
        log_info(f"Result: Expected count_after_both < 5 | Actual count_after_both={count_after_both}")
    log_info("End: advance past second expiry and verify deduction")

def main():
    try:
        log_info("Start: tc15_unlimited_expiration")
        run_step("run variant_expires_mid_level", variant_expires_mid_level)
        run_step("run variant_simultaneous_claims", variant_simultaneous_claims)
        log_info("End: tc15_unlimited_expiration")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_error.png")
    finally:
        teardown_app()

if __name__ == "__main__":
    main()
