# pages/cheat_page.py
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from airtest.core.api import touch, sleep, keyevent, text


class CheatPage(BasePage):
    cheat_menu = get_template("cheat/menu_cheat.png", (-0.422, -0.822))
    close_cheat_menu = get_template("cheat/btn_close_cheat_mode.png", (0.432, -0.821))

    list_cheat_menu = [
        get_template("cheat/btn_system_check.png", (-0.092, -0.611)),
        get_template("cheat/btn_console.png", (-0.075, -0.326)),
        get_template("cheat/btn_options.png", (-0.069, -0.036)),
        get_template("cheat/btn_profiler.png", (-0.071, 0.233)),
    ]

    label_level = get_template("cheat/console/level/jump_to_number.png", (-0.19, 0.004))
    btn_go_to_level = get_template(
        "cheat/console/level/btn_go_to_lv.png", (-0.265, -0.482)
    )
    btn_winlevel = get_template("cheat/console/level/btn_winlv.png", (-0.287, -0.325))
    btn_break_all_piecein_wave = get_template(
        "cheat/console/level/btn_break_all_piecein_wave.png", (-0.124, -0.167)
    )

    speed_button = [
        get_template("cheat/console/auto_play_func/btn_speed_x1.png", (-0.383, 0.057)),
        get_template("cheat/console/auto_play_func/btn_speed_x2.png", (-0.2, 0.057)),
        get_template("cheat/console/auto_play_func/btn_speed_x4.png", (0.006, 0.068)),
        get_template("cheat/console/auto_play_func/btn_speed_x6.png", (0.206, 0.068)),
    ]
    check_box = [
        get_template(
            "cheat/console/auto_play_func/btn_auto_play_off.png", (-0.376, -0.015)
        ),
        get_template(
            "cheat/console/auto_play_func/btn_auto_play_on.png", (-0.381, -0.018)
        ),
    ]
    btn_hack_iap = get_template(
        "cheat/console/iap/hack_IAP.png", record_pos=(-0.208, 0.066)
    )
    btn_reset_daily_mission = get_template(
        "cheat/console/dailymission/btn_reset_daily_mission.png", record_pos=(-0.168, 0.021)
    )
    btn_reset_win_streak = get_template(
        "cheat/console/win_streak/btn_reset_win_streak.png", record_pos=(-0.192, 0.101)
    )
    btn_add_1_streak = get_template(
        "cheat/console/win_streak/btn_add_1_streak.png", record_pos=(-0.075, 0.261)
    )
    btn_add_69_streak = get_template(
        "cheat/console/win_streak/btn_add_69_streak.png", record_pos=(-0.036, 0.414)
    )

    def open_cheat(self) -> None:
        width, height = self.get_screen_size()
        hidden_x = int(360 * width / 720)   # horizontal center (was 50 = left edge)
        hidden_y = int(50 * height / 1280)  # near top (was 640 = vertical middle)
        hidden_button = (hidden_x, hidden_y)
        for _ in range(4):
            touch(hidden_button)
        if not self.wait_for_element(self.cheat_menu, timeout=5):
            raise RuntimeError("Cannot open cheat menu")
        self.tap(self.cheat_menu)
        sleep(1)
        if not self.wait_for_element(self.list_cheat_menu[2], timeout=2.5):
            raise RuntimeError("Cannot find cheat Options tab")
        self.tap(self.list_cheat_menu[2])
        sleep(0.5)

    def close_cheat(self) -> None:
        sleep(1)
        self.tap(self.close_cheat_menu)

    def set_level(self, level: int) -> None:
        for _ in range(2):
            self.swipe("down")
        self.tap(self.label_level)
        keyevent("v2_CONTROL+A")
        keyevent("v2_DELETE")
        text(str(level), True)
        sleep(1)
        self.tap(self.btn_go_to_level)
        sleep(1.5)

    def auto_play_on(self) -> None:
        for _ in range(2):
            self.swipe("down")
        sleep(1)
        self.swipe("up")
        sleep(1)
        self.tap(self.speed_button[1])
        self.tap(self.check_box[0])

    def auto_play_off(self) -> None:
        for _ in range(2):
            self.swipe("down")
        sleep(1)
        self.swipe("up")
        sleep(1)
        self.tap(self.speed_button[0])
        self.tap(self.check_box[1])

    def win_level(self) -> None:
        for _ in range(2):
            self.swipe("down")
        self.tap(self.btn_winlevel)

    def break_all_piecein_wave(self) -> None:
        self.tap(self.btn_break_all_piecein_wave)

    def win_level_and_continue(self) -> bool:
        home = HomePage()
        self.win_level()
        self.close_cheat()
        sleep(1)
        if home.wait_for_element(home.btn_next, timeout=4):
            home.tap(home.btn_next)
            sleep(1)
            return True
        if home.wait_for_element(home.splash_home_icon, timeout=2.5):
            return False
        return False

    def hack_IAP(self) -> None:
        # IAP toggle sits below the fold in the cheat console; scroll to reveal.
        for _ in range(2):
            self.swipe("up")
            sleep(0.5)
        sleep(1)
        self.tap(self.btn_hack_iap)
        self.close_cheat()

    def reset_daily_mission(self) -> None:
        for _ in range(4):
            self.swipe("down")
            sleep(0.5)
        sleep(1)
        
        found = False
        for _ in range(8):
            if self.wait_for_element(self.btn_reset_daily_mission, timeout=0.5):
                found = True
                break
            self.swipe("up")
            sleep(0.5)
            
        if found:
            self.tap(self.btn_reset_daily_mission)
        else:
            raise RuntimeError("Cannot find btn_reset_daily_mission")

        self.close_cheat()

    def _scroll_to_win_streak(self) -> None:
        # win-streak section sits deep in the cheat console: swipe up 6 times.
        for _ in range(6):
            self.swipe("up")
            sleep(0.5)
        sleep(1)
        if not self.wait_for_element(self.btn_add_1_streak, timeout=3):
            raise RuntimeError("Cannot find win-streak cheat section after 6 swipes")

    def cheat_magicbean_progress(self, wins: int) -> None:
        """Add `wins` magicbean streak progress via the cheat console.

        Contract: cheat console already open (call open_cheat() first);
        closes the console before returning.
        """
        self._scroll_to_win_streak()
        for _ in range(wins // 69):
            self.tap(self.btn_add_69_streak)
            sleep(0.5)
        for _ in range(wins % 69):
            self.tap(self.btn_add_1_streak)
            sleep(0.5)
        self.close_cheat()

    def reset_magicbean_streak(self) -> None:
        """Reset magicbean streak to 0 via the cheat console.

        Contract: cheat console already open; closes console before return.
        """
        self._scroll_to_win_streak()
        self.tap(self.btn_reset_win_streak)
        sleep(0.5)
        self.close_cheat()
