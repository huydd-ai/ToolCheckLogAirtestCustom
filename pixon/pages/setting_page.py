# pages/setting_page.py
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from airtest.core.api import sleep
from pixon.common import wrappers as wrapper


class SettingPage(BasePage):
    btn_setting = get_template("system_function/btn_setting.png", (0.425, -0.811))
    btn_music = get_template("settings_page/btn_music.png", (0.164, -0.208))
    btn_sound = get_template("settings_page/btn_sound.png", (0.181, -0.094))
    btn_vibrate = get_template("settings_page/btn_vibrate.png", (0.181, 0.018))
    btn_zoom = get_template("settings_page/btn_zoom.png", (-0.4, 0.556))
    btn_redeem_code_blue = get_template(
        "settings_page/btn_redeem_code_blue.png", (-0.014, -0.061)
    )
    btn_save_progress = get_template(
        "settings_page/btn_save_progress.png", (-0.003, 0.097)
    )
    btn_delete_progress = get_template(
        "settings_page/btn_delete_progress.png", (0.003, 0.042)
    )
    blank_confirm = get_template("settings_page/blank_confirm.png", (0.003, 0.064))
    label_setting = get_template("settings_page/label_setting.png", (0.003, -0.594))
    # ponytail: in-level Setting restart button uses the shared TRY AGAIN pill (user-confirmed)
    btn_restart = get_template("system_function/btn_try_again.png", (0.0, 0.0))
    btn_home_quit = get_template("system_function/btn_home.png", (0.0, 0.0))

    def open_setting(self, retry: int = 3) -> bool:
        home = HomePage()
        for attempt in range(retry):
            if wrapper.wait_exists(home.btn_close, timeout=0.15):
                self.tap(home.btn_close)
                sleep(0.25)
            self.tap(self.btn_setting)
            if self.wait_for_element(self.btn_save_progress, timeout=1.5):
                return True
        return False

    def music(self) -> None:
        if self.btn_music:
            self.tap(self.btn_music)

    def sound(self) -> None:
        if self.btn_sound:
            self.tap(self.btn_sound)

    def vibrate(self) -> None:
        if self.btn_vibrate:
            self.tap(self.btn_vibrate)

    def redeem_code(self) -> None:
        self.tap(self.btn_redeem_code_blue)

    def save_progress(self) -> None:
        self.tap(self.btn_save_progress)

    def delete_progress(self, word: str = "confirm") -> None:
        home = HomePage()
        if not self.open_setting():
            raise AssertionError("delete_progress: cannot open settings panel")
        self.save_progress()
        if not self.wait_for_element(self.btn_delete_progress, timeout=5):
            raise AssertionError("delete_progress: btn_delete_progress not found")
        self.tap(self.btn_delete_progress)
        if not self.wait_for_element(self.blank_confirm, timeout=7):
            self.take_screenshot("blank_confirm_error.png")
            wrapper.log_error("delete_progress: blank_confirm input not found")
            raise AssertionError("delete_progress: blank_confirm input not found")
        self.tap(self.blank_confirm)
        self.input_text(str(word), confirm=True)
        self.tap(home.btn_delete)

    def restart_level(self) -> bool:
        """In-level Setting -> Restart. Returns False if panel/button not found."""
        if not self.open_setting():
            return False
        if not self.wait_for_element(self.btn_restart, timeout=5):
            return False
        self.tap(self.btn_restart)
        return True

    def quit_to_home(self) -> bool:
        """In-level Setting -> Home. Returns False if panel/button not found."""
        if not self.open_setting():
            return False
        if not self.wait_for_element(self.btn_home_quit, timeout=5):
            return False
        self.tap(self.btn_home_quit)
        return True
