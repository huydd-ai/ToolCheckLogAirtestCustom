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
)
from pixon.common.adb_utils import cold_start_with_combined, set_combined, set_param
from pixon.common import config

home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()

def variant_from_rewards():
    # TC27 — Unlimited heart granted by Daily Reward / Spin / Mission / Battle Pass
    log_info("Start: setup heart test (heart=3, level=12, coin=5000)")
    profile = {
        "fakeads": True,
        "heart": 3,
        "level": 12,
        "coin": 5000,
        "booster": {"drill": 20, "hammer": 20, "magnet": 20},
        "playspeed": config.GAME_START_PLAY_SPEED,
        "server_sync": False,
    }
    run_step("cold start with heart profile", cold_start_with_combined, **profile)
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: setup heart test")

    log_info("Start: verify unlimited not active before grant")
    unlimited_active = heart_page.is_unlimited_hearts_active()
    if unlimited_active:
        raise AssertionError(
            "Unlimited heart already active before test - unexpected state"
        )
    else:
        log_info(f"Result: Expected unlimited_active=False | Actual unlimited_active={unlimited_active}")
    log_info("End: verify unlimited not active before grant")

    log_info("Warm send unlimited heart via ADB")
    run_step("set combined unlimited heart", set_combined, heart="unlimited")
    sleep(3)
    run_step("clear any triggered popups", close_all_popups, home_page)
    unlimited_active = heart_page.is_unlimited_hearts_active(timeout=5)
    if not unlimited_active:
        raise AssertionError(
            "Unlimited heart badge NOT visible after granting unlimited heart"
        )
    else:
        log_info(f"Result: Expected unlimited_active=True | Actual unlimited_active={unlimited_active}")
    log_info("End: grant unlimited heart and verify badge")

def variant_from_events():
    # TC28 — Event grants +1 heart (or unlimited)
    log_info("Start: setup heart test (heart=2, level=12, coin=5000)")
    profile = {
        "fakeads": True,
        "heart": 2,
        "level": 12,
        "coin": 5000,
        "booster": {"drill": 20, "hammer": 20, "magnet": 20},
        "playspeed": config.GAME_START_PLAY_SPEED,
        "server_sync": False,
    }
    run_step("cold start with heart profile", cold_start_with_combined, **profile)
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: setup heart test")

    log_info("Start: grant +1 heart via event and verify")
    count_before = heart_page.get_heart_count_via_ocr()
    run_step("set param heart +1", set_param, "heart", count_before + 1)
    sleep(3)
    run_step("clear any triggered popups", close_all_popups, home_page)
    count_after = heart_page.get_heart_count_via_ocr()
    if count_after <= count_before and not heart_page.is_unlimited_hearts_active():
        raise AssertionError(
            f"Event heart reward had no effect: before={count_before}, after={count_after}"
        )
    else:
        log_info(f"Result: Expected count_after > {count_before} | Actual count_after={count_after}")
    log_info("End: grant +1 heart via event and verify")

def main():
    try:
        log_info("Start: tc15_unlimited_grants")
        run_step("run variant_from_rewards", variant_from_rewards)
        run_step("run variant_from_events", variant_from_events)
        log_info("End: tc15_unlimited_grants")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_error.png")
    finally:
        teardown_app(__file__)

if __name__ == "__main__":
    main()
