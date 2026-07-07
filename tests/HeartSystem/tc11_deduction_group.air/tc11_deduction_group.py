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
from pixon.common.adb_utils import cold_start_with_combined, warm_send_json, set_param, run_adb_command, cold_start_with_json
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def lose_level(home) -> None:
    log_info("Start: lose_level")
    run_step("trigger lose outcome", set_param, "set_level_win", False)
    sleep(1.5)
    for attempt in range(10):
        wrapper.log_info(f"lose_level: tapping btn_close (attempt {attempt + 1})")
        home.tap(home.btn_close)
        sleep(0.75)
        if home.is_at_home():
            break
    log_info("End: lose_level")


def quit_to_home(home) -> None:
    log_info("Start: quit_to_home")
    home.go_home(force=True)
    sleep(1)
    run_step("navigate to home", go_home_clean, home)
    log_info("End: quit_to_home")


def enter_game(home, timeout: int = 20) -> None:
    log_info("Start: enter_game")
    run_step("click play", home.click_play)
    sleep(5)
    log_info("End: enter_game")


# -------------------- variant bodies (only middle differs) --------------------


def variant_lose_no_revive():
    # TC18 — Endgame Lose No Revive -> 1 heart deducted
    log_info("Start: variant_lose_no_revive")
    lose_level(home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: variant_lose_no_revive")


def variant_quit_to_home():
    # TC19 — Quit to home during gameplay -> 1 heart deducted
    log_info("Start: variant_quit_to_home")
    sleep(2)
    quit_to_home(home_page)
    log_info("End: variant_quit_to_home")


def variant_restart_midgame():
    # TC20 — Restart mid-game -> 1 heart deducted
    log_info("Start: variant_restart_midgame")
    run_step("Autoplay", warm_send_json, {"autoplay":True})
    sleep(4)
    stop_app("com.woodpuzzle.pin3d")
    sleep(2)
    run_step("cold start app", cold_start_with_json, {"fakeads": True, "playspeed": 6, "clear_data": False, "server_sync": False})
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    log_info("End: variant_restart_midgame")

def variant_background_close():
    # TC22 — Background then swipe-close -> 1 heart deducted
    log_info("Start: variant_background_close")
    sleep(2)
    run_step("press home key", run_adb_command, ["shell", "input", "keyevent", "KEYCODE_HOME"])
    sleep(2)
    run_step("force-stop app", run_adb_command, ["shell", "am", "force-stop", "com.woodpuzzle.pin3d"])
    sleep(5)
    stop_app("com.woodpuzzle.pin3d")
    run_step("cold start app", cold_start_with_json, {"fakeads": True, "playspeed": 6, "clear_data": False, "server_sync": False})
    sleep(30)
    run_step("close startup popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)
    log_info("End: variant_background_close")


# -------------------- shared driver --------------------


def run_variant(label, variant_fn):
    run_step("warm send heart=5", warm_send_json, {"heart": 5})
    sleep(2)
    run_step("navigate to home", go_home_clean, home_page)
    count_before = heart_page.get_heart_count_via_ocr()
    enter_game(home_page)
    variant_fn()
    count_after = heart_page.get_heart_count_via_ocr()
    if count_after != count_before - 1:
        raise AssertionError(
            f"{label}: expected heart={count_before - 1} after interrupt, got {count_after}"
        )
    else:
        log_info(f"Result: Expected count_after={count_before - 1} | Actual count_after={count_after}")


def main():
    try:
        log_info("Start: setup heart test (heart=5, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 5,
            "level": 12,
            "coin": 5000,
            "playspeed": config.GAME_START_PLAY_SPEED,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        log_info("Start: TC18 lose_no_revive — deduction on endgame lose")
        run_step("run variant_lose_no_revive", run_variant, "TC18 lose_no_revive", variant_lose_no_revive)
        log_info("End: TC18 lose_no_revive")
        sleep(5)

        log_info("Start: TC19 quit_to_home — deduction on quit")
        run_step("run variant_quit_to_home", run_variant, "TC19 quit_to_home", variant_quit_to_home)
        log_info("End: TC19 quit_to_home")
        sleep(5)

        log_info("Start: TC20 restart_midgame — deduction on restart")
        run_step("run variant_restart_midgame", run_variant, "TC20 restart_midgame", variant_restart_midgame)
        log_info("End: TC20 restart_midgame")
        sleep(5)

        log_info("Start: TC21 background_close — deduction on background+kill")
        run_step("run variant_background_close", run_variant, "TC21 background_close", variant_background_close)
        log_info("End: TC21 background_close")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC11_error: {str(e)}")
        snapshot(filename="tc11_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
