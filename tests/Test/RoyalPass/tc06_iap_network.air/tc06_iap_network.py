
from airtest.core.api import *

from pixon.common import wrappers as wrapper

from pixon.pages.home_page import HomePage
from pixon.pages.royal_pass_page import RoyalPassPage

from pixon.common.test_flow import (
    run_step,
    teardown_app,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import cold_start_with_json, set_param, disable_wifi, enable_wifi


home_page = HomePage()
royal_pass = RoyalPassPage()




home_page = HomePage()

royal_pass = RoyalPassPage()





def main():

    # STT 11 — IAP attempt with no network → handled gracefully, no crash.

    try:

        # open_app_for_royal_pass(home_page, level=16)

        run_step(

            "cold start at level 15 for Royal Pass unlock",

            cold_start_with_json,

            {"fakeads": True, "level": 15, "coin": 10000, "playspeed": 6},

        )

        sleep(30)

        run_step("close all popups after launch", close_all_popups, home_page)

        run_step("navigate home after launch", go_home_clean, home_page)

        run_step("enter level 15 by clicking play", home_page.click_play)

        sleep(5)

        run_step("win level 15 to unlock level 16 + Royal Pass", set_param, "set_level_win", True)

        sleep(1.5)

        run_step("return home to unlock Royal Pass", home_page.click_btn_next)

        sleep(2.5)

        run_step("ensure clean home screen after level transition", go_home_clean, home_page)



        if not home_page.wait_for_element(home_page.btn_main_home, timeout=5):

            raise AssertionError("Home screen did not load")



        disable_wifi()

        sleep(5)



        if not royal_pass.open_royal_pass_popup():

            raise AssertionError("Royal Pass popup did not open while offline")



        royal_pass.tap(royal_pass.collect_all_btn)



        if not royal_pass.wait_for_element(royal_pass.premium_banner, timeout=8):

            raise AssertionError("Premium pack popup not visible while offline")



        sleep(5)

    except Exception as e:

        wrapper.log_error(f"TC06_error: {str(e)}")

        snapshot(filename="tc06_error.png")

    finally:

        enable_wifi()

        teardown_app()





if __name__ == "__main__":

    main()
