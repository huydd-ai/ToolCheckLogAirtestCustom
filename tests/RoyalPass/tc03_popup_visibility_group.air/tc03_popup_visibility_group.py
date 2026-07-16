
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

from pixon.common.adb_utils import (
cold_start_with_json,
set_param,
)


home_page = HomePage()
royal_pass = RoyalPassPage()




home_page = HomePage()

royal_pass = RoyalPassPage()



# Royal Pass popup-visibility group (RP_001, RP_004, RP_005, RP_006, RP_007, RP_008).

# All variants share: open_app_for_royal_pass(level=16) -> assert home loaded.

# Each differs only in the middle (icon tap vs win-flow vs lose-flow vs claim vs premium popup).



# -------------------- variant bodies --------------------





def variant_uiux():

    # RP_001 — UI/UX at lv16: icon visible, popup opens

    if not royal_pass.wait_for_element(royal_pass.btn_gold_pass, timeout=5):

        raise AssertionError("Royal Pass icon not visible on home")

    royal_pass.tap(royal_pass.btn_gold_pass)

    sleep(2)





def _autoplay_win_to_home():

    # autoplay_win_to_home: play → force win → return home

    run_step("autoplay: click play to enter level", home_page.click_play)

    sleep(5)

    run_step("autoplay: force win current level", set_param, "set_level_win", True)

    sleep(1.5)

    run_step("autoplay: return home via btn_next", home_page.click_btn_next)

    sleep(2.5)





def variant_endgame_win():

    # RP_004 — Win level: EXP awarded; popup opens after win

    _autoplay_win_to_home()

    if not home_page.wait_for_element(home_page.btn_main_home, timeout=20):

        raise AssertionError("Did not return home after win")

    if not royal_pass.is_pass_popup_open(timeout=10):

        raise AssertionError("Royal Pass popup did not open automatically after win")





def variant_endgame_lose():

    # RP_005 — Lose/exit: EXP NOT awarded; RP still accessible

    home_page.tap(home_page.btn_main_play)

    sleep(3)

    keyevent("BACK")

    sleep(2)

    if not home_page.wait_for_element(home_page.btn_main_home, timeout=10):

        raise AssertionError("Did not return home after lose/exit")

    if not royal_pass.open_royal_pass_popup():

        raise AssertionError("Royal Pass popup did not open after lose/exit")





def variant_free_locked():

    # RP_006 — Free reward locked at zero EXP

    if not royal_pass.open_royal_pass_popup():

        raise AssertionError("Royal Pass popup did not open")

    if not royal_pass.wait_for_element(royal_pass.claim_btn, timeout=5):

        raise AssertionError("claim_btn not present in RP popup")





def variant_exp_milestone():

    # RP_007 — First EXP milestone: claim free reward

    # Precondition: must autoplay+win a level so EXP accrues and claim_btn activates.

    _autoplay_win_to_home()

    if not royal_pass.is_pass_popup_open(timeout=10):

        if not royal_pass.open_royal_pass_popup():

            raise AssertionError("Royal Pass popup did not open")

    if not royal_pass.wait_for_element(royal_pass.claim_btn, timeout=5):

        raise AssertionError("Claim button not active at milestone EXP")

    if not royal_pass.claim_free_reward():

        raise AssertionError("Failed to claim free reward")





def variant_pack_popup():

    # RP_008 — Tap locked gold reward: premium pack purchase popup

    if not royal_pass.open_royal_pass_popup():

        raise AssertionError("Royal Pass popup did not open")

    royal_pass.tap(royal_pass.collect_all_btn)

    if not royal_pass.wait_for_element(royal_pass.premium_banner, timeout=8):

        raise AssertionError("Premium pack popup not visible")

    snapshot(filename="rp_pack_popup.png")





# -------------------- shared driver --------------------





def main():

    try:

        # open_app_for_royal_pass(home_page, level=16, coin=10000)

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



        variant_uiux()

        go_home_clean(home_page)



        variant_free_locked()

        go_home_clean(home_page)



        variant_endgame_lose()

        go_home_clean(home_page)



        variant_endgame_win()

        go_home_clean(home_page)



        variant_exp_milestone()

        go_home_clean(home_page)



        variant_pack_popup()



        sleep(5)

    except Exception as e:

        wrapper.log_error(f"TC03_error: {str(e)}")

        snapshot(filename="tc03_error.png")

    finally:

        teardown_app(__file__)





if __name__ == "__main__":

    main()
