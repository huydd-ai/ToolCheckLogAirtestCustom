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
from pixon.common.adb_utils import cold_start_with_combined, warm_send_json
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 29 — Shop: "Out of Hearts" special packages displayed when heart=0
    try:
        log_info("Start: setup heart test (heart=1, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 1,
            "level": 12,
            "coin": 5000,
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

        log_info("Start: set heart to 0")
        run_step("warm send heart to 0", warm_send_json, {"heart": 0})
        sleep(2)
        log_info("End: set heart to 0")

        log_info("Start: trigger out-of-hearts popup")
        run_step("click play", home_page.click_play)
        sleep(2)

        popup_visible = heart_page.is_out_of_hearts_popup_visible(timeout=10)
        if not popup_visible:
            raise AssertionError("Out-of-hearts popup did not appear when heart=0")
        else:
            log_info(f"Result: Expected popup_visible=True | Actual popup_visible={popup_visible}")
        log_info("End: trigger out-of-hearts popup")

        log_info("Start: check shop out-of-hearts packages")
        packs_visible = heart_page.wait_for_element(
            heart_page.shop_out_of_hearts_pack, timeout=5
        )
        if not packs_visible:
            raise AssertionError("Out-of-hearts shop packages not visible in popup")
        else:
            log_info(f"Result: Expected shop_out_of_hearts_pack=visible | Actual shop_out_of_hearts_pack={packs_visible}")
        log_info("End: check shop out-of-hearts packages")

        log_info("Start: check general heart packages visible in shop")
        general_packs_visible = heart_page.wait_for_element(heart_page.shop_heart_pack, timeout=5)
        if not general_packs_visible:
            raise AssertionError("General heart packages not visible in popup")
        else:
            log_info(f"Result: Expected shop_heart_pack=visible | Actual shop_heart_pack={general_packs_visible}")
        log_info("End: check general heart packages visible in shop")

        log_info("Start: dismiss popup")
        run_step("tap close button", home_page.tap, home_page.btn_close)
        sleep(1)
        log_info("End: dismiss popup")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC16_error: {str(e)}")
        snapshot(filename="tc16_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
