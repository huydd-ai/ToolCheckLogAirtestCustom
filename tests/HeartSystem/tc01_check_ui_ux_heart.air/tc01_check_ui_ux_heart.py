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
from pixon.common.adb_utils import cold_start_with_combined
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 1 — Check UI/UX of heart system
    try:
        log_info("Start: setup heart test (heart=5, level=12, coin=5000)")
        profile = {
            "heart": 5,
            "level": 12,
            "coin": 5000,
            "playspeed": config.GAME_START_PLAY_SPEED,
            "fakeads": True,
            "clear_data": True,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup heart test")

        log_info("Start: check heart icon visible")
        icon_visible = heart_page.wait_for_element(heart_page.icon_heart, timeout=5)
        if not icon_visible:
            raise AssertionError("Expected heart icon to be visible, got False")
        else:
            log_info(f"Result: Expected icon_heart=visible | Actual icon_heart={icon_visible}")
        log_info("End: check heart icon visible")

        log_info("Start: check heart count label visible")
        label_visible = heart_page.wait_for_element(heart_page.label_heart_count, timeout=5)
        if not label_visible:
            raise AssertionError("Expected heart count label to be visible, got False")
        else:
            log_info(f"Result: Expected label_heart_count=visible | Actual label_heart_count={label_visible}")
        log_info("End: check heart count label visible")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC01_error: {str(e)}")
        snapshot(filename="tc01_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
