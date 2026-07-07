
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

        log_info("Start: Change avatar")
        current = profile_page.get_current_avatar()
        new_avatar = profile_page.change_avatar(current)
        profile_page.verify_avatar(new_avatar)

        log_info("End: Change avatar")
        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC_change_avatar_error: {str(e)}")
        snapshot(filename="tc_change_avatar_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
