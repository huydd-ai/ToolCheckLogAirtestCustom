import random
import string

from airtest.core.api import *
from pixon.common.wrappers import log_info
from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.player_profile import PlayerProfilePage
from pixon.common.test_flow import run_step, teardown_app, go_home_clean
from pixon.common.adb_utils import cold_start_with_combined
from pixon.common import config

home_page = HomePage()
profile_page = PlayerProfilePage()


def random_string(max_len=11):
    length = random.randint(5, max_len)
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def main():
    try:
        # open_app_with_fake_ads: cold start with default profile
        run_step(
            "cold start app with profile payload",
            cold_start_with_combined,
            fakeads=True,
            heart=config.GAME_START_HEART,
            level=config.GAME_START_LEVEL,
            booster={
                "drill": config.GAME_START_DRILL,
                "hammer": config.GAME_START_HAMMER,
                "magnet": config.GAME_START_MAGNET,
            },
            coin=config.GAME_START_COIN,
            playspeed=config.GAME_START_PLAY_SPEED,
            clear_data=True,
            server_sync=False,
        )
        sleep(30)

        log_info("Start: Go home clean")
        go_home_clean(home_page)

        log_info("Start: Change player name")
        name = random_string()
        wrapper.try_touch(profile_page.profile_corner)
        wrapper.try_touch(profile_page.edit_button)
        wrapper.try_touch(profile_page.edit_button)
        wrapper.try_touch(profile_page.name_corner)
        sleep(1)
        home_page.input_text(name)
        wrapper.try_touch(profile_page.continue_button)

        log_info("End: Change player name")
        if not wrapper.is_text_present(name, (335, 421, 738, 526)):
            wrapper.log_error("Change name verify fail!")
            snapshot(filename="tc_change_name_fail.png")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC_change_name_error: {str(e)}")
        snapshot(filename="tc_change_name_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
