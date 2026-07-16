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
from pixon.common.adb_utils import cold_start_with_combined, set_time_relative
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    try:
        log_info("Start: setup (heart=3, level=3, coin=10000)")
        profile = {
            "fakeads": True,
            "heart": 4,
            "level": 12,
            "coin": 10000,
            "booster": {"drill": 20, "hammer": 20, "magnet": 20},
            "playspeed": config.GAME_START_PLAY_SPEED,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup")

        log_info("Start: wait for home screen")
        home_visible = home_page.wait_for_element(home_page.btn_main_play, timeout=30)
        if not home_visible:
            raise AssertionError("WAIT_FOR timed out for btn_main_home")
        else:
            log_info(f"Result: Expected btn_main_play=visible | Actual btn_main_play={home_visible}")
        log_info("End: wait for home screen")

        log_info("Start: verify initial heart count")
        heart_count = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count = {heart_count}")
        if heart_count != 4:
            raise AssertionError(f"Expected heart count 4, got {heart_count}")
        else:
            log_info(f"Result: Expected heart_count=4 | Actual heart_count={heart_count}")
        run_step("verify heart refill timer", heart_page.verify_heart_refill_timer)
        log_info("End: verify initial heart count")

        log_info("Start: stop app and advance clock and verify regen")
        run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
        run_step("advance clock by 1.0 hours", set_time_relative, 1.0)
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
        heart_count_after = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count after wait = {heart_count_after}")
        if heart_count_after <= 4:
            raise AssertionError(
                f"Passive regen did not increase heart count: before={heart_count}, after={heart_count_after}"
            )
        else:
            log_info(f"Result: Expected heart_count_after > 4 | Actual heart_count_after={heart_count_after}")
        run_step("verify heart refill timer", heart_page.verify_heart_refill_timer)
        sleep(5)
        log_info("End: advance clock and verify regen")
    except Exception as e:
        wrapper.log_error(f"TC23_error: {str(e)}")
        snapshot(filename="tc23_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
