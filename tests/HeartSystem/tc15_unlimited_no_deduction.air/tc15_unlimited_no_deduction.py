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
from pixon.common.adb_utils import cold_start_with_combined, cold_start_with_json, run_adb_command, set_param
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

def quit_to_home(home) -> None:
    home.go_home(force=True)
    sleep(1)
    go_home_clean(home)

def variant_no_deduction_active():
    # TC25 — Lose / Quit / Kill during Unlimited -> no heart deducted
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

    log_info("Start: verify no heart deducted on lose")
    if not heart_page.is_unlimited_hearts_active():
        wrapper.log_info("Unlimited heart badge not visible - proceeding anyway")
    count_before = heart_page.get_heart_count_via_ocr()

    run_step("click play", home_page.click_play)
    sleep(5)
    lose_level(home_page)
    run_step("navigate to home after lose", go_home_clean, home_page)
    count_after_lose = heart_page.get_heart_count_via_ocr()
    if count_after_lose != count_before:
        raise AssertionError(
            f"Heart deducted on lose during unlimited (before={count_before})"
        )
    else:
        log_info(f"Result: Expected count_after_lose={count_before} | Actual count_after_lose={count_after_lose}")
    log_info("End: verify no heart deducted on lose")

    log_info("Start: verify no heart deducted on quit")
    run_step("click play", home_page.click_play)
    sleep(5)
    quit_to_home(home_page)
    count_after_quit = heart_page.get_heart_count_via_ocr()
    if count_after_quit != count_before:
        raise AssertionError(
            f"Heart deducted on quit during unlimited (before={count_before})"
        )
    else:
        log_info(f"Result: Expected count_after_quit={count_before} | Actual count_after_quit={count_after_quit}")
    log_info("End: verify no heart deducted on quit")

    log_info("Start: verify no heart deducted on kill")
    run_step("click play", home_page.click_play)
    # Wait long enough for the game's autosave to persist the heart state
    sleep(15)
    run_step("force stop app", run_adb_command, ["shell", "am", "force-stop", "com.woodpuzzle.pin3d"])
    sleep(5)
    run_step("teardown app", teardown_app)
    run_step("cold start app", cold_start_with_json, {"fakeads": True, "playspeed": 6, "clear_data": False, "server_sync": False})
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home after kill", go_home_clean, home_page)
    count_after_kill = heart_page.get_heart_count_via_ocr()
    if count_after_kill != count_before:
        raise AssertionError(
            f"Heart deducted on kill during unlimited (before={count_before})"
        )
    else:
        log_info(f"Result: Expected count_after_kill={count_before} | Actual count_after_kill={count_after_kill}")
    log_info("End: verify no heart deducted on kill")

def main():
    try:
        log_info("Start: tc15_unlimited_no_deduction")
        run_step("run variant_no_deduction_active", variant_no_deduction_active)
        log_info("End: tc15_unlimited_no_deduction")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC15_error: {str(e)}")
        snapshot(filename="tc15_error.png")
    finally:
        teardown_app(__file__)

if __name__ == "__main__":
    main()
