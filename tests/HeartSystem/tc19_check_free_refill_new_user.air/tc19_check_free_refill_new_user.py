from pixon.common.wrappers import log_info

from airtest.core.api import *
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.game_page import GamePage
from pixon.pages.heart_system_page import HeartSystemPage
from pixon.pages.setting_page import SettingPage
from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)
from pixon.common.adb_utils import (
    cold_start_with_combined,
    warm_send_json,
)
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()
setting = SettingPage()


def main():
    # FLW-03: fresh install, heart=0, tap play, tap Free Refill, verify hearts=5
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
        log_info("End: setup")

        log_info("Start: simulate new user autoplay game")
        run_step("warm send after clear data", warm_send_json, {"fakeads": True, "autoplay": True, "playspeed": config.GAME_START_PLAY_SPEED})
        sleep(10)
        run_step("set param heart to 1 and disable autoplay", warm_send_json, {"heart": 1, "autoplay": False})
        run_step("navigate to home after reset", go_home_clean, home_page)
        log_info("End: simulate new user")

        log_info("Start: tap play to trigger out-of-hearts popup")
        run_step("click play", home_page.click_play)
        sleep(2)

        popup_visible = heart_page.is_out_of_hearts_popup_visible(timeout=10)
        if not popup_visible:
            raise AssertionError("Out-of-hearts popup did not appear when heart=0")
        else:
            log_info(f"Result: Expected popup_visible=True | Actual popup_visible={popup_visible}")
        log_info("End: tap play to trigger out-of-hearts popup")

        log_info("Start: tap Free Refill and verify hearts restored")
        tap_ok = heart_page.tap_refill()
        if not tap_ok:
            raise AssertionError("Could not tap Free Refill button")
        else:
            log_info(f"Result: Expected tap_refill=True | Actual tap_refill={tap_ok}")
        sleep(3)
        run_step("navigate to home after refill", go_home_clean, home_page)

        count = heart_page.get_heart_count_via_ocr()
        if count != 4:
            raise AssertionError(
                f"Free refill did not restore hearts and auto-start properly: count={count} (expected 4)"
            )
        else:
            log_info(f"Result: Expected count=4 | Actual count={count}")
        log_info("End: tap Free Refill and verify hearts restored")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC19_error: {str(e)}")
        snapshot(filename="tc19_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
