# pages/home_page.py
from pixon.common.test_flow import teardown_app
from pixon.pages.base_page import BasePage, get_template
from pathlib import Path
from airtest.core.api import sleep
from pixon.common import wrappers as wrapper
from pixon.common.adb_utils import cold_start_with_json, wait_for_app_ready
import time

IMAGE_DIR = Path(__file__).resolve().parent / "images"


class HomePage(BasePage):
    splash_screen_icon = get_template("splash_screen_icon.png", (0.051, -0.164))
    splash_home_icon = get_template("label_main_home.png", (-0.006, 0.792))
    btn_main_home = get_template("home_page/btn_main_home.png", (-0.004, 0.799))
    btn_main_play = get_template("home_page/btn_play.png", (0.003, 0.497))
    btn_lucky_spin = get_template("home_page/btn_lucky_spin.png", (-0.401, -0.364))
    btn_setting = get_template("system_function/btn_setting.png", (0.425, -0.811))
    btn_home = get_template("system_function/btn_home.png", (-0.01, 0.357))
    btn_close = get_template("system_function/btn_close.png", (0.365, -0.861))
    btn_tutorial = get_template("system_function/btn_tutorial.png", (-0.415, -0.799))
    btn_next = get_template("system_function/btn_next.png", (-0.003, 0.086))
    btn_delete = get_template("system_function/btn_delete.png", (-0.001, 0.201))
    label_setting = get_template("settings_page/label_setting.png", (0.003, -0.594))
    btn_store = get_template("home_page/btn_store_page.png", (-0.333, 0.804))
    heart_count_full = get_template(
        "heart_system/heart_count_full.png", (-0.068, -0.818)
    )
    btn_starter_pack = get_template("home_page/btn_starter_pack.png", (0.406, -0.026))
    btn_toy_adventure = get_template(
        "home_page/btn_toy_adventure.png", (-0.397, -0.383)
    )
    btn_dream_trail = get_template("home_page/btn_dream_trail.png", (0.417, -0.046))
    btn_milestone = get_template("home_page/btn_milestone.png", (0.408, 0.128))
    tap_to_claim = get_template("tap_to_claim.png", (0.001, 0.506))
    btn_piggy = get_template("piggy/btn_piggy_icon.png", (0.394, -0.567))
    btn_free_ads = get_template("home_page/btn_free_ads.png", (-0.401, -0.22))

    def is_at_home(self) -> bool:
        end_time = time.time() + 1
        while time.time() < end_time:
            if wrapper.partial_search(self.splash_home_icon):
                return True
            sleep(0.05)
        return False

    def _tap_overlay_action(
        self, template, label: str, max_attempts: int = 1, delay: float = 0.125
    ) -> bool:
        tapped = False
        for _ in range(max_attempts):
            if not wrapper.partial_search(template):
                break
            self.tap(template)
            sleep(delay)
            tapped = True
        return tapped

    def _is_screen_dark(self) -> bool:
        from pixon.common import wrappers as _w
        import numpy as np

        screen = _w.get_screen()
        if screen is None:
            return False
        mean_brightness = float(np.mean(screen))
        is_dark = mean_brightness < 30
        if is_dark:
            wrapper.log_warning(
                f"_is_screen_dark: brightness={mean_brightness:.1f} — screen too dark to navigate"
            )
        return is_dark

    def _get_daily_mission_page(self):
        from pixon.pages.daily_mission import DailyMissionPage

        if not hasattr(self, "_daily_mission_cache"):
            self._daily_mission_cache = DailyMissionPage()
        return self._daily_mission_cache

    def _try_in_app_home_navigation(self, retries: int = 6) -> bool:
        """Navigate to home using only in-app buttons detected by Airtest templates."""
        daily_page = self._get_daily_mission_page()
        stuck_count = 0
        last_signature = None

        for i in range(retries):
            acted = False

            acted |= self._tap_overlay_action(
                daily_page.tap_to_continue,
                "tap_to_continue",
                max_attempts=3,
                delay=0.05,
            )
            if wrapper.partial_search(daily_page.btn_collect):
                self.tap(daily_page.btn_collect)
                sleep(2)
                if wrapper.partial_search(self.tap_to_claim):
                    self.tap(self.tap_to_claim)
                    sleep(0.2)
                acted = True
            acted |= self._tap_overlay_action(self.btn_close, "close_btn")
            acted |= self._tap_overlay_action(self.btn_setting, "btn_setting")
            acted |= self._tap_overlay_action(
                self.btn_home, "btn_home", max_attempts=2, delay=0.2
            )

            if wrapper.partial_search(self.label_setting):
                self._tap_overlay_action(self.btn_close, "close_btn_after_setting")

            if self.is_at_home():
                return True

            signature = (
                int(bool(wrapper.partial_search(daily_page.tap_to_continue))),
                int(bool(wrapper.partial_search(daily_page.btn_collect))),
                int(bool(wrapper.partial_search(self.btn_close))),
                int(bool(wrapper.partial_search(self.btn_main_home))),
                int(bool(wrapper.partial_search(self.btn_main_play))),
            )
            if signature == last_signature and not acted:
                stuck_count += 1
            else:
                stuck_count = 0
            last_signature = signature

            if stuck_count >= 2:
                wrapper.log_info(
                    "go_home: state unchanged across attempts, breaking early"
                )
                break

        return False

    def go_home(self, force: bool = False) -> bool:
        if not force and self.is_at_home():
            return True
        if self._is_screen_dark():
            wrapper.log_info("go_home: screen dark — waiting 0.5s before retry")
            sleep(0.5)
            if self.is_at_home():
                return True

        if self._try_in_app_home_navigation(retries=6):
            return True

        wrapper.log_info("go_home: in-app navigation failed, restarting app once")
        teardown_app()
        sleep(1)
        cold_start_with_json({"fakeads": True, "playspeed": 6})
        
        wait_for_app_ready()

        if self._try_in_app_home_navigation(retries=6):
            return True

        wrapper.log_info("go_home: all approaches failed after restart")
        return False

    def click_play(self) -> None:
        self.tap(self.btn_main_play)

    def close_popup(self) -> None:
        coord = wrapper.partial_search(self.btn_close)
        if coord:
            self.tap(coord)

    def click_btn_next(self) -> None:
        for _ in range(3):
            if self.wait_for_element(self.btn_next, timeout=1.5):
                self.tap(self.btn_next)
                return
            wrapper.log_error("btn_next not visible, retrying...")
            sleep(0.5)
        wrapper.log_error("btn_next not found after 3 retries")
        self.tap(self.btn_next)
