from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from airtest.core.api import sleep
from airtest.aircv import crop_image
from pixon.common import wrappers as wrapper
import re


class RoyalPassPage(BasePage):
    btn_gold_pass = get_template("home_page/btn_gold_pass.png", (0.404, -0.026))
    pass_entry_icon = get_template("royal_pass/pass_entry_icon.png", (0.0, 0.2))
    collect_all_btn = get_template("royal_pass/collect_all_btn.png", (0.0, 0.4))
    claim_btn = get_template("royal_pass/claim_btn.png", (-0.1, 0.3))
    premium_banner = get_template("royal_pass/premium_banner.png", (0.0, -0.583))
    tier_track = get_template("royal_pass/tier_track.png", (-0.167, -0.393))
    xp_bar = get_template("royal_pass/xp_bar.png", (-0.032, -0.392))

    XP_AREA = (300, 500, 400, 550)
    TIER_AREA = (200, 300, 520, 360)

    def is_pass_entry_visible(self, timeout=2.5) -> bool:
        return bool(self.wait_for_element(self.pass_entry_icon, timeout=timeout))

    def is_premium_active(self, timeout=1.5) -> bool:
        return bool(self.wait_for_element(self.premium_banner, timeout=timeout))

    def is_pass_popup_open(self, timeout=2.5) -> bool:
        if self.wait_for_element(self.pass_entry_icon, timeout=timeout):
            return True
        if self.wait_for_element(self.tier_track, timeout=0.5):
            return True
        return False

    def open_royal_pass_popup(self) -> bool:
        if not self.wait_for_element(self.btn_gold_pass, timeout=2.5):
            wrapper.log_warning("open_royal_pass_popup: btn_gold_pass not found")
            return False
        self.tap(self.btn_gold_pass)
        if self.wait_for_element(self.pass_entry_icon, timeout=2.5):
            return True
        if self.wait_for_element(self.tier_track, timeout=1):
            return True
        wrapper.log_warning("open_royal_pass_popup: pass popup did not appear")
        return False

    def close_royal_pass(self) -> bool:
        home = HomePage()
        return bool(self.tap(home.btn_close))

    def collect_all_rewards(self) -> bool:
        if not self.wait_for_element(self.collect_all_btn, timeout=5):
            wrapper.log_warning("collect_all_rewards: collect_all_btn not found")
            return False
        return bool(self.tap(self.collect_all_btn))

    def claim_free_reward(self) -> bool:
        if not self.wait_for_element(self.claim_btn, timeout=2.5):
            return False
        self.tap(self.claim_btn)
        sleep(0.5)
        return True

    def get_xp_via_ocr(self) -> int:
        @wrapper.retry(times=3, delay=1, exceptions=(Exception,))
        def _attempt():
            screen = wrapper.get_screen()
            w, h = self.get_screen_size()
            x1, y1, x2, y2 = self.XP_AREA
            scaled = (
                int(x1 * w / 720),
                int(y1 * h / 1280),
                int(x2 * w / 720),
                int(y2 * h / 1280),
            )
            cropped = crop_image(screen, scaled)
            texts = wrapper.find_all_text(cropped)
            if texts:
                for t in texts:
                    m = re.search(r"\d+", t)
                    if m:
                        return int(m.group())
            return 0

        return _attempt()

    def get_tier_via_ocr(self) -> int:
        @wrapper.retry(times=3, delay=1, exceptions=(Exception,))
        def _attempt():
            screen = wrapper.get_screen()
            w, h = self.get_screen_size()
            x1, y1, x2, y2 = self.TIER_AREA
            scaled = (
                int(x1 * w / 720),
                int(y1 * h / 1280),
                int(x2 * w / 720),
                int(y2 * h / 1280),
            )
            cropped = crop_image(screen, scaled)
            texts = wrapper.find_all_text(cropped)
            if texts:
                for t in texts:
                    m = re.search(r"\d+", t)
                    if m:
                        return int(m.group())
            return 0

        return _attempt()

    def _find_all_elements(self, template, timeout=0.5) -> list:
        screen = wrapper.get_screen()
        pos = template.match_all_in(screen)
        return pos if pos else []

    btn_active_gold_pass = pass_entry_icon
    btn_collect_all = collect_all_btn
    btn_free_ads = claim_btn
    def open_royal_pass(self) -> bool:
        return self.open_royal_pass_popup()

    def is_active_gold_pass_visible(self, timeout=2.5) -> bool:
        return self.is_pass_entry_visible(timeout=timeout)
