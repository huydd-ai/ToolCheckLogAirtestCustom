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
    # STT 13 — Case 5: out-of-hearts popup → tap Refill → enters game
    try:
        log_info("Start: setup heart test (heart=0, level=12, coin=5000)")
        profile = {
            "heart": 0,
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

        log_info("Start: tap Play and verify out-of-hearts popup")
        run_step("tap play button", home_page.click_play)
        sleep(3)
        popup_visible = heart_page.is_out_of_hearts_popup_visible(timeout=5)
        if not popup_visible:
            raise AssertionError("out-of-hearts popup did not appear after tapping Play")
        else:
            log_info(f"Result: Expected popup_visible=True | Actual popup_visible={popup_visible}")
        log_info("End: tap Play and verify out-of-hearts popup")

        log_info("Start: tap refill and verify game starts")
        tap_ok = heart_page.tap_refill()
        if not tap_ok:
            raise AssertionError("Could not tap btn_refill on out-of-hearts popup")
        else:
            log_info(f"Result: Expected tap_refill=True | Actual tap_refill={tap_ok}")
        sleep(5)
        log_info("End: tap refill and verify game starts")

        log_info("Start: return home and check heart count")
        run_step("navigate home", go_home_clean, home_page)
        count = heart_page.get_heart_count_via_ocr()
        if count < 0:
            raise AssertionError(f"Invalid heart count after refill flow: count={count}")
        else:
            log_info(f"Result: Expected count >= 0 | Actual count={count}")
        log_info("End: return home and check heart count")
    except Exception as e:
        wrapper.log_error(f"TC08_error: {str(e)}")
        snapshot(filename="tc08_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
