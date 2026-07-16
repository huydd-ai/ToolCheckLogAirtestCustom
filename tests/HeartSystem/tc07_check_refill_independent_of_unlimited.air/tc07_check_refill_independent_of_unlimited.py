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
from pixon.common.adb_utils import cold_start_with_combined, set_time_relative, set_combined, run_adb_command, resume_app
from pixon.common import config


home_page = HomePage()
game = GamePage()
heart_page = HeartSystemPage()


def main():
    # STT 12 — Case 4: heart refill process is independent of unlimited heart timer
    # Setup: heart=3, unlimited_heart active for 30 min
    # Wait 30 min → unlimited expires → verify refill timer resumes for missing hearts
    try:
        log_info("Start: setup (heart=3, level=12, coin=5000, unlimited_heart=True)")
        profile = {
            "fakeads": True,
            "heart": 3,
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
        
        log_info("Apply unlimited heart via ADB")
        run_step("warm send unlimited heart", set_combined, heart="unlimited")
        sleep(5)
        
        log_info("Start: verify unlimited timer decreasing from ~1h")
        timer_str = heart_page.get_heart_timer_str_via_ocr()
        try:
            seconds_left = heart_page.parse_timer_to_seconds(timer_str)
            if not (3500 <= seconds_left <= 3600):
                raise AssertionError(f"Unlimited timer not ~1 hour: {timer_str} ({seconds_left}s)")
            else:
                log_info(f"Result: Expected 3500 <= timer <= 3600 | Actual timer={seconds_left}s")
            
            sleep(3)
            timer_str_2 = heart_page.get_heart_timer_str_via_ocr()
            seconds_left_2 = heart_page.parse_timer_to_seconds(timer_str_2)
            
            if seconds_left_2 >= seconds_left:
                raise AssertionError(f"Timer is not decreasing! {seconds_left} -> {seconds_left_2}")
            else:
                log_info(f"Result: Expected timer_left < {seconds_left} | Actual timer_left={seconds_left_2}")
                log_info(f"Result: Unlimited timer is decreasing correctly: {timer_str} -> {timer_str_2}")
        except Exception as e:
            raise AssertionError(f"Failed to verify unlimited timer: {e}")
        log_info("End: verify unlimited timer decreasing from ~1h")

        log_info("End: setup")

        log_info("Start: advance clock by 1 hour to expire unlimited heart")
        
        # 1. Step back to home (background the app)
        run_step("send app to background", run_adb_command, ["shell", "input", "keyevent", "KEYCODE_HOME"])
        sleep(2)
        
        # 2. Advance clock by 1 hour so unlimited heart expires
        ok = run_step("advance clock by 1 hour", set_time_relative, 1.0)
        if not ok:
            wrapper.log_error(
                "set_time_relative failed — clock not advanced (check LDPlayer ROOT toggle)"
            )
        sleep(5)
        
        # 3. Open app with package name (bring to foreground without intent)
        run_step("bring app to foreground", resume_app)
        sleep(5)
        
        log_info("End: advance clock")

        log_info("Start: navigate to home after time advance")
        run_step("navigate to home after time advance", go_home_clean, home_page)
        log_info("End: navigate to home after time advance")

        log_info("Start: verify refill timer visible after unlimited expires")
        # After unlimited expires, heart should still be at 3 (was not depleted during unlimited)
        # and refill timer should be visible
        visible = heart_page.is_heart_timer_visible(timeout=10)
        if not visible:
            raise AssertionError(
                "Heart refill timer not visible after unlimited heart expired"
            )
        else:
            log_info(f"Result: Expected timer_visible=True | Actual timer_visible={visible}")
        log_info("End: verify refill timer visible after unlimited expires")

        log_info("Start: verify heart count in bounds")
        count = heart_page.get_heart_count_via_ocr()
        if count > 5 or count < 0:
            raise AssertionError(f"Heart count out of bounds: {count}")
        else:
            log_info(f"Result: Expected 0 <= count <= 5 | Actual count={count}")
        log_info("End: verify heart count in bounds")

        sleep(5)
    except Exception as e:
        wrapper.log_error(f"TC07_error: {str(e)}")
        snapshot(filename="tc07_error.png")
    finally:
        teardown_app(__file__)


if __name__ == "__main__":
    main()
