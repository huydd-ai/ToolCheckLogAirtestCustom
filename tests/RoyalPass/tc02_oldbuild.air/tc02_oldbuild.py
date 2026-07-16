
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

from pixon.common.adb_utils import cold_start_with_json


home_page = HomePage()
royal_pass = RoyalPassPage()




home_page = HomePage()

royal_pass = RoyalPassPage()





def main():

    # STT 3 — Old build user below level 16 → no Royal Pass popup.

    try:

        # open_app_for_royal_pass(home_page, level=10) — level < 16, simple path

        run_step(

            "cold start at level 10 (below unlock)",

            cold_start_with_json,

            {"fakeads": True, "level": 10, "coin": 10000, "playspeed": 6},

        )

        sleep(30)

        run_step("close all popups after launch", close_all_popups, home_page)

        run_step("navigate home after launch", go_home_clean, home_page)



        if not home_page.wait_for_element(home_page.btn_main_home, timeout=5):

            raise AssertionError("Home screen did not load")



        if not home_page.wait_for_element(home_page.btn_main_play, timeout=5):

            raise AssertionError("Main play button not visible at level 10")



        if royal_pass.wait_for_element(royal_pass.btn_gold_pass, timeout=2):

            raise AssertionError("Royal Pass icon should NOT appear below level 16")



        sleep(5)

    except Exception as e:

        wrapper.log_error(f"TC02_error: {str(e)}")

        snapshot(filename="tc02_error.png")

    finally:

        teardown_app(__file__)





if __name__ == "__main__":

    main()
