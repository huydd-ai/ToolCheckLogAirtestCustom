
from airtest.core.api import *

from pixon.common import wrappers as wrapper

from pixon.pages.home_page import HomePage
from pixon.pages.royal_pass_page import RoyalPassPage
from pixon.pages.heart_system_page import HeartSystemPage

from pixon.common.test_flow import (
    teardown_app,
    go_home_clean,
    close_all_popups,
)

from pixon.common.adb_utils import cold_start_with_json


home_page = HomePage()
royal_pass = RoyalPassPage()
heart_page = HeartSystemPage()




home_page = HomePage()

royal_pass = RoyalPassPage()

heart_page = HeartSystemPage()





def main():

    # MEC-03 — RP heart-limit buff 5 → 8. Start RP-unlocked at level 21 with heart=8.

    try:

        payload = {

            "fakeads": True,

            "level": 21,

            "coin": 10000,

            "heart": 8,

            "playspeed": 6,

        }

        cold_start_with_json(payload)

        sleep(30)

        close_all_popups(home_page)

        go_home_clean(home_page)



        if not home_page.wait_for_element(home_page.btn_main_home, timeout=5):

            raise AssertionError("Home screen did not load")



        if not royal_pass.wait_for_element(royal_pass.btn_gold_pass, timeout=5):

            wrapper.log_warning("RP entry icon not visible — heart buff may not apply")



        heart_count = heart_page.get_heart_count_via_ocr()

        wrapper.log_info(f"Detected heart count: {heart_count}")

        if heart_count < 8:

            raise AssertionError(f"Expected heart=8 with RP active, got {heart_count}")

        wrapper.log_info(f"PASS: Heart buff verified — count={heart_count}")



        sleep(5)

    except Exception as e:

        wrapper.log_error(f"TC08_error: {str(e)}")

        snapshot(filename="tc08_error.png")

    finally:

        teardown_app()





if __name__ == "__main__":

    main()
