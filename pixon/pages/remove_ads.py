# pages/remove_ads.py
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from airtest.core.api import sleep


class RemoveAds(BasePage):
    btn_fake_ads_off = get_template(
        "cheat/console/ads/btn_fake_ads_off.png", (-0.25, 0.41)
    )
    btn_fake_ads_on = get_template(
        "cheat/console/ads/btn_fake_ads_on.png", (-0.256, 0.407)
    )
    btn_remove_ads = get_template("btn_remove_ads.png", (-0.294, -0.804))

    def fake_ads_on(self):
        for _ in range(10):
            self.swipe("up")
            sleep(0.15)
        self.tap(self.btn_fake_ads_off)
        for _ in range(10):
            self.swipe("down")
            sleep(0.15)
