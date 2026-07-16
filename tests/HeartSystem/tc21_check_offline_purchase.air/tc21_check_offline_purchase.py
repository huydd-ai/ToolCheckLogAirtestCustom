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
from pixon.common.adb_utils import cold_start_with_combined, network_disconnect, network_reconnect, warm_send_json
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # EDG-03 — Offline purchase: buy heart refill while airplane mode, verify persist after reconnect
    try:
        log_info("Start: setup (heart=1, level=12, coin=5000)")
        profile = {
            "fakeads": True,
            "heart": 1,
            "level": 12,
            "coin": 5000,
            "booster": {"drill": 20, "hammer": 20, "magnet": 20},
            "playspeed": config.GAME_START_PLAY_SPEED,
            "server_sync": False,
        }
        run_step("cold start with heart profile", cold_start_with_combined, **profile)
        sleep(30)
        run_step("close startup popups", close_all_popups, home_page)
        run_step("navigate to home", go_home_clean, home_page)
        log_info("End: setup")

        log_info("Start: set heart to 0 via warm send")
        run_step("warm send heart to 0", warm_send_json, {"heart": 0})

        log_info("Start: read heart count before offline purchase")
        count_before = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count before offline purchase: {count_before}")
        log_info("End: read heart count before offline purchase")

        log_info("Start: disconnect network")
        run_step("disconnect network", network_disconnect)
        sleep(3)
        log_info("End: disconnect network")

        log_info("Start: trigger out-of-hearts popup")
        run_step("click play", home_page.click_play)
        sleep(3)
        popup_visible = heart_page.is_out_of_hearts_popup_visible(timeout=10)
        if not popup_visible:
            raise AssertionError(
                "Out-of-hearts popup did not appear when heart=0 offline"
            )
        else:
            log_info(f"Result: Expected popup_visible=True | Actual popup_visible={popup_visible}")
        log_info("End: trigger out-of-hearts popup")

        log_info("Start: tap refill while offline")
        tap_ok = heart_page.tap_refill()
        if not tap_ok:
            raise AssertionError("Could not tap refill button while offline")
        else:
            log_info(f"Result: Expected tap_refill=True | Actual tap_refill={tap_ok}")
        sleep(3)
        log_info("End: tap refill while offline")

        log_info("Start: verify heart count increased after offline refill")
        run_step("ensure app is at home after refill", go_home_clean, home_page)
        count_after = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count after offline refill: {count_after}")
        if count_after <= count_before:
            raise AssertionError(
                f"Offline refill did not add hearts: before={count_before}, after={count_after}"
            )
        else:
            log_info(f"Result: Expected count_after > {count_before} | Actual count_after={count_after}")
        log_info("End: verify heart count increased after offline refill")

        log_info("Start: reconnect and verify state persists")
        run_step("reconnect network", network_reconnect)
        sleep(3)
        count_reconnect = heart_page.get_heart_count_via_ocr()
        wrapper.log_info(f"Heart count after reconnect: {count_reconnect}")
        if count_reconnect != count_after:
            wrapper.log_warning(
                f"Heart count changed after reconnect: {count_after} → {count_reconnect}"
            )
        else:
            log_info(f"Result: Expected count_reconnect={count_after} | Actual count_reconnect={count_reconnect}")
        log_info("End: reconnect and verify state persists")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC21_error: {str(e)}")
        snapshot(filename="tc21_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
