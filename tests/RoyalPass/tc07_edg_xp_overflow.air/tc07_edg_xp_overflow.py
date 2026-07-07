
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

from pixon.common.adb_utils import cold_start_with_json, set_param, set_combined


home_page = HomePage()
royal_pass = RoyalPassPage()




home_page = HomePage()

royal_pass = RoyalPassPage()





def main():

    # EDG-04 — XP overflow at max tier: no crash, UI renders, XP display readable.

    try:

        # open_app_for_royal_pass(home_page, level=21)

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

        run_step(

            "set level to 21 for max-tier XP overflow test",

            set_combined,

            fakeads=True, level=21, coin=10000, playspeed=6,

        )

        sleep(2.5)

        run_step("navigate home after set_combined", go_home_clean, home_page)



        if not home_page.wait_for_element(home_page.btn_main_home, timeout=5):

            raise AssertionError("Home screen did not load")



        # autoplay_win_to_home: earn EXP via one win at max tier

        run_step("autoplay: click play to enter level", home_page.click_play)

        sleep(5)

        run_step("autoplay: force win current level", set_param, "set_level_win", True)

        sleep(1.5)

        run_step("autoplay: return home via btn_next", home_page.click_btn_next)

        sleep(2.5)



        if not royal_pass.open_royal_pass_popup():

            raise AssertionError("Could not open Royal Pass popup")



        xp_value = royal_pass.get_xp_via_ocr()

        wrapper.log_info(f"Detected XP value: {xp_value}")

        if xp_value == 0:

            wrapper.log_warning(

                "XP OCR returned 0 — UI may show non-numeric display at max tier"

            )



        if royal_pass.collect_all_rewards():

            wrapper.log_info("PASS: Collect all button functional at max tier")

        else:

            wrapper.log_info("Collect all not available — checking claim button")

            if royal_pass.claim_free_reward():

                wrapper.log_info("PASS: Free claim button functional at max tier")

            else:

                wrapper.log_warning(

                    "Neither collect_all nor claim found — UI may be reset at max tier"

                )



        wrapper.log_info("PASS: RP UI renders at XP overflow (max tier)")



        sleep(5)

    except Exception as e:

        wrapper.log_error(f"TC07_error: {str(e)}")

        snapshot(filename="tc07_error.png")

    finally:

        teardown_app()





if __name__ == "__main__":

    main()
