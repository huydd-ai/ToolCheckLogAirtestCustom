# pages/lucky_spin.py
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from airtest.core.api import sleep


class LuckySpinPage(BasePage):
    btn_spin = get_template("lucky_spin/btn_spin.png", (-0.001, 0.528))
    label_lucky_spin = get_template("lucky_spin/label_lucky_spin.png", (0.004, -0.644))

    def roll_out(self) -> None:
        home = HomePage()
        home.tap(home.btn_lucky_spin)
        self.spin()
        sleep(2)
        home.tap(home.btn_close)

    def spin(self) -> None:
        self.wait_for_element(self.btn_spin, timeout=10)
        self.tap(self.btn_spin)
        sleep(3)
