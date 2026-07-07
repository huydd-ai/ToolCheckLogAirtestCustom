from pixon.pages.base_page import BasePage, get_template
from pathlib import Path
from airtest.core.api import G
from airtest.aircv import crop_image
from pixon.common import wrappers as wrapper

IMAGE_DIR = Path(__file__).resolve().parent / "images"


class PlayerProfilePage(BasePage):
    # TODO: MISSING_IMAGE — capture from device and save to pages/images/player_profile/
    # Required images:
    #   player_profile/btn_edit.png         — edit button on profile screen
    #   player_profile/btn_save.png         — save button on profile screen
    #   player_profile/corner_profile.png   — profile avatar corner area
    #   player_profile/corner_name.png      — name display corner area
    #   player_profile/icon_tick.png        — tick/checkmark icon for avatar selection
    #   player_profile/avatar_1.png through avatar_9.png — 9 avatar options

    home_play_button = get_template("home_page/btn_play.png", (0.003, 0.497))
    setting_icon = get_template("system_function/btn_setting.png", (0.425, -0.811))
    go_home_button = get_template("system_function/btn_home.png", (-0.01, 0.357))
    close_button = get_template("system_function/btn_close.png", (0.365, -0.861))
    save_button = get_template("player_profile/btn_save.png", (-0.004, 0.629))
    continue_button = get_template("tap_to_continue.png", (0.0, 0.0))
    edit_button = get_template("player_profile/btn_edit.png", (0.0, 0.0))
    profile_corner = get_template("player_profile/corner_profile.png", (0.0, 0.0))
    name_corner = get_template("player_profile/corner_name.png", (0.0, 0.0))
    tick_v = get_template("player_profile/icon_tick.png", (0.0, 0.0))
    list_avatar = [
        get_template(f"player_profile/avatar_{i}.png", (0.0, 0.0)) for i in range(1, 10)
    ]

    def go_home(self):
        if not wrapper.wait_exists(self.home_play_button, 1.5):
            wrapper.try_touch(self.setting_icon)
            wrapper.try_touch(self.go_home_button)
            wrapper.try_touch(self.go_home_button)
            wrapper.wait_exists(self.home_play_button, 2.5)

    def get_current_avatar(self):
        screen = G.DEVICE.snapshot()
        local_screen = crop_image(screen, (0, 0, 200, 200))
        for av in self.list_avatar:
            if av.match_in(local_screen):
                return av
        wrapper.log_error("Cannot find current avatar!", True)
        return None

    def change_avatar(self, current_avatar):
        list_filtered = [x for x in self.list_avatar if x != current_avatar]
        import random

        new_avatar = random.choice(list_filtered)
        wrapper.try_touch(current_avatar)
        wrapper.try_touch(self.edit_button)
        wrapper.try_touch(new_avatar)
        wrapper.try_touch(self.save_button)
        wrapper.try_touch(self.close_button)
        wrapper.try_touch(self.close_button)
        return new_avatar

    def verify_avatar(self, img):
        if not wrapper.wait_exists(img, 2.5):
            raise AssertionError("Verify avatar fail in home screen")
        wrapper.try_touch(img)
        if not wrapper.wait_exists(img, 2.5):
            raise AssertionError("Verify avatar fail in profile screen")
        wrapper.try_touch(self.edit_button)
        if not wrapper.wait_exists(img, 2.5):
            raise AssertionError("Verify avatar fail in profile editing screen")
