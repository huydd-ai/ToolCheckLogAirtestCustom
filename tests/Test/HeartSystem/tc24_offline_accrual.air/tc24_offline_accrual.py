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
from pixon.common.adb_utils import cold_start_with_combined, set_time_relative
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    try:
        # STT 1 — Heart count refills correctly even while the game is closed (offline accrual)
        log_info("Start: setup heart test (heart=2, level=3, coin=10000)")
        profile = {
            "fakeads": True,
            "heart": 3,
            "level": 12,
            "playspeed": config.GAME_START_PLAY_SPEED,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        log_info("Start: verify home screen visible")
        home_visible = home_page.wait_for_element(home_page.btn_main_play, timeout=30)
        if not home_visible:
            raise AssertionError("WAIT_FOR timed out for btn_main_home")
        else:
            log_info(f"Result: Expected btn_main_play=visible | Actual btn_main_play={home_visible}")
        log_info("End: verify home screen visible")

        log_info("Start: verify initial heart count is 3")
        heart_count = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count = {heart_count}")
        if heart_count != 3:
            raise AssertionError(f"Expected heart count 3, got {heart_count}")
        else:
            log_info(f"Result: Expected heart_count=3 | Actual heart_count={heart_count}")
        run_step("verify heart refill timer", heart_page.verify_heart_refill_timer)
        log_info("End: verify initial heart count is 3")

        log_info("Start: stop app and advance clock by 1 hour")
        run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
        run_step("advance clock by 1.0 hours", set_time_relative, 1.0)
        log_info("End: stop app and advance clock by 1 hour")

        log_info("Start: reopen app (no heart reset) and verify offline accrual")
        reopen_profile = {
            "fakeads": True,
            "level": 12,
            "playspeed": config.GAME_START_PLAY_SPEED,
        }
        run_step("cold start without heart reset", cold_start_with_combined, **reopen_profile, clear_data=False, server_sync=False)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: reopen app (no heart reset)")

        log_info("Start: verify home screen visible after reopen")
        home_visible = home_page.wait_for_element(home_page.btn_main_play, timeout=30)
        if not home_visible:
            raise AssertionError("WAIT_FOR timed out for btn_main_home")
        else:
            log_info(f"Result: Expected btn_main_play=visible | Actual btn_main_play={home_visible}")
        log_info("End: verify home screen visible after reopen")

        log_info("Start: verify heart count increased after offline accrual")
        heart_count_after = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count after offline wait = {heart_count_after}")
        if heart_count_after <= 3:
            raise AssertionError(
                f"Expected heart count to refill offline, got {heart_count_after}"
            )
        else:
            log_info(f"Result: Expected heart_count_after > 3 | Actual heart_count_after={heart_count_after}")
        run_step("verify heart refill timer", heart_page.verify_heart_refill_timer)
        log_info("End: verify heart count increased after offline accrual")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC24_error: {str(e)}")
        snapshot(filename="tc24_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
