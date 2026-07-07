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
    # STT 5 — Check heart refills by waiting time (1 heart per 20 min, max=5)
    try:
        log_info("Start: setup heart test (heart=3, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 3,
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

        log_info("Start: record heart count before time advance")
        count_before = heart_page.get_heart_count_via_ocr()
        log_info(f"Heart count before: {count_before}")
        log_info("End: record heart count before time advance")

        log_info("Start: stop app and advance clock by 1 hour")
        run_step("stop app", stop_app, "com.woodpuzzle.pin3d")
        run_step("advance clock by 1 hour", set_time_relative, 1.0)
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
        log_info("End: stop app and advance clock by 1 hour")

        log_info("Start: verify heart count increased after time advance")
        count_after = heart_page.get_heart_count_via_ocr()
        log_info(f"Heart count after: {count_after}")
        if count_after <= count_before:
            raise AssertionError(
                f"Expected heart to refill: before={count_before}, after={count_after}"
            )
        else:
            log_info(f"Result: Expected count_after > {count_before} | Actual count_after={count_after}")
        log_info("End: verify heart count increased after time advance")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC05_error: {str(e)}")
        snapshot(filename="tc05_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
