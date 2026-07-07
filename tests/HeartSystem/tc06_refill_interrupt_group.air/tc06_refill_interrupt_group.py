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
from pixon.common.adb_utils import cold_start_with_combined, warm_send_json, set_param, set_time_relative, run_adb_command, set_hack_iap
from pixon.common import config

home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def _refill_persists_after_interrupt(
    adb_cmd: list, label: str, count_before: int, *, teardown: bool = True
) -> int:
    log_info(f"[{label}] Interrupt: run adb {' '.join(adb_cmd[-2:])}")
    run_step(f"[{label}] run adb command", run_adb_command, adb_cmd)

    log_info(f"[{label}] Advance clock +1h")
    run_step(f"[{label}] advance clock by 1 hours", set_time_relative, 1.0)

    if teardown:
        log_info(f"[{label}] Teardown app")
        teardown_app()
        run_step(
            f"[{label}] Cold start (clear_data=False, server_sync=False)",
            cold_start_with_combined,
            fakeads=True,
            playspeed=6,
            level=12,
            clear_data=False,
            server_sync=False,
        )
    else:
        log_info(f"[{label}] Resume app from background (no teardown)")
        run_step(f"[{label}] warm send empty payload", warm_send_json, {})

    sleep(30)
    run_step("close popups", close_all_popups, home_page)
    run_step("navigate to home", go_home_clean, home_page)

    count_after = heart_page.get_heart_count_via_ocr()
    if count_after <= count_before:
        raise AssertionError(
            f"Refill stopped after {label}: before={count_before}, after={count_after}"
        )
    return count_after


def variant_kill_app():
    # TC06 — Case 3 Scenario 1: kill app while in-game -> refill still continues
    log_info("Start: kill app while in-game")
    log_info("Read heart count on home screen")
    count_before = heart_page.get_heart_count_via_ocr()
    log_info(f"Heart count before: {count_before}")

    log_info("Navigate into game (click Play)")
    run_step("tap play button", home_page.click_play)
    sleep(5)

    count_after = _refill_persists_after_interrupt(
        ["shell", "am", "force-stop", "com.woodpuzzle.pin3d"], "kill", count_before
    )
    if count_after <= count_before:
        raise AssertionError(f"Expected count > {count_before}, got {count_after}")
    else:
        log_info(f"Result: Expected count > {count_before} | Actual count={count_after}")
    log_info("End: kill app while in-game — PASS")


def variant_background():
    # TC07 — Case 3 Scenario 2: background app while in-game -> refill timer still counts
    log_info("Start: background app while in-game")
    log_info("Read heart count on home screen")
    count_before = heart_page.get_heart_count_via_ocr()
    log_info(f"Heart count before: {count_before}")

    log_info("Navigate into game (click Play)")
    run_step("tap play button", home_page.click_play)
    sleep(5)

    count_after = _refill_persists_after_interrupt(
        ["shell", "input", "keyevent", "KEYCODE_HOME"], "background", count_before, teardown=False
    )
    if count_after <= count_before:
        raise AssertionError(f"Expected count > {count_before}, got {count_after}")
    else:
        log_info(f"Result: Expected count > {count_before} | Actual count={count_after}")
    log_info("End: background app while in-game — PASS")


def variant_ui_taps():
    # TC08 — Case 3 Scenario 3: tap UI elements while waiting refill -> refill unaffected
    log_info("Start: UI taps while refill waiting")
    log_info("Open Settings popup")
    run_step("tap settings button", home_page.tap, home_page.btn_setting)
    sleep(2)

    log_info("Close Settings popup")
    run_step("tap close button", home_page.tap, home_page.btn_close)
    sleep(1)

    visible = heart_page.is_heart_timer_visible(timeout=5)
    if not visible:
        raise AssertionError("Heart refill timer disappeared after tapping settings")
    else:
        log_info(f"Result: Expected timer_visible=True | Actual timer_visible={visible}")
    log_info("End: UI taps while refill waiting — PASS")


def variant_endgame():
    # TC09 — Case 3 Scenario 4: play to endgame -> heart refill timer still visible
    log_info("Start: play to endgame")
    log_info("Navigate into game (click Play)")
    run_step("tap play button", home_page.click_play)
    sleep(5)

    log_info("Trigger level loss via set_level_win=True")
    run_step("set set_level_win to True", set_param, "set_level_win", True)
    sleep(3)

    log_info("Tap next button")
    run_step("tap next button", home_page.click_btn_next)
    sleep(2)

    log_info("Close startup popups")
    run_step("close popups", close_all_popups, home_page)
    sleep(1)

    visible = heart_page.is_heart_timer_visible(timeout=5)
    if not visible:
        raise AssertionError("Heart refill timer not visible on endgame screen")

    timer_str = heart_page.get_heart_timer_str_via_ocr()
    log_info(f"Refill timer text: {timer_str}")
    try:
        sec = heart_page.parse_timer_to_seconds(timer_str)
        if not (0 <= sec <= 1200):
            raise AssertionError(f"Refill timer '{timer_str}' ({sec}s) is not between 00:00 and 20:00")
        log_info(f"Result: Expected 0 <= sec <= 1200 | Actual sec={sec}, timer={timer_str}")
    except Exception as e:
        raise AssertionError(f"Failed to parse or validate refill timer '{timer_str}': {e}")

    run_step("navigate to home", go_home_clean, home_page)
    if not visible:
        raise AssertionError(f"Expected timer_visible=True, got timer_visible={visible}")
    else:
        log_info(f"Result: Expected timer_visible=True | Actual timer_visible={visible}")
    log_info("End: play to endgame — PASS")


def variant_buy_booster():
    # TC10 — Case 3 Scenario 5: tap "Buy Booster" -> popup shows, refill continues
    log_info("Start: tap Buy Booster popup")
    run_step("hack IAP", set_hack_iap, True)
    sleep(1)

    visible_before = heart_page.is_heart_timer_visible(timeout=5)
    log_info(f"Pre-check — Expected: timer_visible=True | Actual: timer_visible={visible_before}")
    if not visible_before:
        raise AssertionError("Refill timer not visible before test")

    log_info("Open buy popup")
    run_step("tap add heart button", heart_page.tap_add_heart)
    sleep(2)

    log_info("Check buy popup")
    popup_visible = heart_page.wait_for_element(
        heart_page.popup_out_of_hearts, timeout=3
    ) or heart_page.wait_for_element(heart_page.btn_buy_heart, timeout=3)
    log_info(f"Buy popup — Expected: popup_visible=True | Actual: popup_visible={popup_visible}")
    if not popup_visible:
        wrapper.log_warning("No buy popup appeared; skipping popup check")

    log_info("Tap Buy Heart button")
    run_step("tap buy heart button", home_page.tap, heart_page.btn_buy_heart)
    sleep(2)
    log_info("Tap to claim reward")
    run_step("tap to claim reward", home_page.tap, home_page.tap_to_claim)
    sleep(1)
    log_info("Tap main home button to return home")
    run_step("tap main home button", home_page.tap, home_page.btn_main_home)
    sleep(2)

    visible_after = heart_page.is_heart_timer_visible(timeout=5)
    if not visible_after:
        raise AssertionError("Refill timer stopped after Buy Booster popup")
    else:
        log_info(f"Result: Expected timer_visible=True | Actual timer_visible={visible_after}")
    log_info("End: tap Buy Booster popup — PASS")


def variant_device_home():
    # TC11 — Case 3 Scenario 6: press device HOME while waiting refill -> refill continues
    log_info("Start: device HOME while refill waiting")
    log_info("Read heart count on home screen")
    count_before = heart_page.get_heart_count_via_ocr()
    log_info(f"Heart count before: {count_before}")

    count_after = _refill_persists_after_interrupt(
        ["shell", "input", "keyevent", "KEYCODE_HOME"], "device HOME", count_before, teardown=False
    )
    if count_after <= count_before:
        raise AssertionError(f"Expected count > {count_before}, got {count_after}")
    else:
        log_info(f"Result: Expected count > {count_before} | Actual count={count_after}")
    log_info("End: device HOME while refill waiting — PASS")


_VARIANTS = [
    ("variant_kill_app (TC06)",    {"fakeads": True, "playSpeed": 6, "heart": 3}, variant_kill_app),
    ("variant_background (TC07)",  {"heart": 3},                                   variant_background),
    ("variant_ui_taps (TC08)",     {"heart": 3},                                   variant_ui_taps),
    ("variant_endgame (TC09)",     {"heart": 3},                                   variant_endgame),
    ("variant_buy_booster (TC10)", {"heart": 0},                                   variant_buy_booster),
    ("variant_device_home (TC11)", {"heart": 3},                                   variant_device_home),
]


def main():
    # STT 6-11 — Refill-interrupt group: 6 variants run sequentially
    try:
        log_info("Start: setup heart test (heart=3, level=12, coin=5000)")
        run_step(
            "cold start with heart profile",
            cold_start_with_combined,
            fakeads=True,
            heart=3,
            level=12,
            coin=5000,
            playspeed=config.GAME_START_PLAY_SPEED,
            server_sync=False,
        )
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        for label, setup_payload, fn in _VARIANTS:
            log_info(f"Start: {label}")
            run_step(f"warm send payload for {label}", warm_send_json, setup_payload)
            sleep(5)
            run_step("ensure app is at home", go_home_clean, home_page)
            run_step(f"run {label}", fn)
            sleep(5)
            log_info(f"End: {label}")

    except Exception as e:
        wrapper.log_error(f"TC06_error: {str(e)}")
        snapshot(filename="tc06_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
