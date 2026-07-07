# pages/heart_system_page.py
from pixon.pages.base_page import BasePage, get_template
from pathlib import Path
from airtest.core.api import sleep, G
from pixon.common import wrappers as wrapper
import time

IMAGE_DIR = Path(__file__).resolve().parent / "images"


class HeartSystemPage(BasePage):
    # TODO: MISSING_IMAGE — 1×1 placeholder stubs still need real captures:
    #   heart_system/btn_buy_heart.png       — original buy-heart btn (shadowed by btn_buy_IAP)
    # All other images (icon_heart, label_heart_count, label_heart_timer, label_unlimited,
    # btn_refill, btn_watch_rv, popup_out_of_hearts, popup_refill, shop_heart_pack,
    # shop_out_of_hearts_pack) are captured and real.

    icon_heart = get_template("heart_system/icon_heart.png", (-0.16, -0.809))
    btn_add_heart = get_template("heart_system/btn_add_heart.png", (-0.126, -0.805))
    btn_buy_heart_by_coin = get_template("heart_system/btn_buy_heart_by_coin.png", (0.0, 0.07))
    label_heart_count = get_template(
        "heart_system/label_heart_count.png", (-0.12, -0.81)
    )
    label_heart_timer = get_template(
        "heart_system/label_heart_timer.png", (-0.026, -0.809)
    )
    label_unlimited = get_template("heart_system/label_unlimited.png", (-0.149, -0.818))
    btn_refill = get_template("heart_system/btn_refill.png", (0.006, 0.0))
    btn_watch_rv = get_template("heart_system/btn_watch_rv.png", (0.0, 0.2))
    popup_out_of_hearts = get_template(
        "heart_system/popup_out_of_hearts.png", (-0.001, -0.625)
    )
    popup_refill = get_template("heart_system/popup_refill.png", (0.006, 0.0))
    shop_heart_pack = get_template("heart_system/shop_heart_pack.png", (0.001, 0.272))
    shop_out_of_hearts_pack = get_template(
        "heart_system/shop_out_of_hearts_pack.png", (-0.01, -0.361)
    )
    btn_claim_by_ads = get_template("heart_system/btn_claim_by_ads.png", (-0.019, 0.656))
    btn_buy_heart = get_template("system_function/btn_buy_IAP.png", (0.253, -0.36))

    def get_heart_system_zone(self) -> list:
        w, h = self.get_screen_size()
        return [int(w * 0.28), 0, int(w * 0.57), int(h * 0.09)]

    def get_heart_icon_zone(self) -> list:
        w, h = self.get_screen_size()
        return [int(w * 0.28), 0, int(w * 0.40), int(h * 0.09)]

    def get_heart_timer_zone(self) -> list:
        w, h = self.get_screen_size()
        return [int(w * 0.38), 0, int(w * 0.57), int(h * 0.09)]

    def is_out_of_hearts_popup_visible(self, timeout: int = 5) -> bool:
        return self.wait_for_element(self.popup_out_of_hearts, timeout=timeout)

    def is_unlimited_hearts_active(self, timeout: int = 3) -> bool:
        return self.wait_for_element(self.label_unlimited, timeout=timeout)

    def is_heart_timer_visible(self, timeout: int = 5) -> bool:
        if self.wait_for_element(self.label_heart_timer, timeout=0.5):
            return True
        from pixon.pages.home_page import HomePage

        home = HomePage()
        if not home.is_at_home():
            home.go_home()
        start = time.time()
        from airtest.aircv import crop_image
        import re

        while time.time() - start < timeout:
            screen = G.DEVICE.snapshot()
            zone = self.get_heart_timer_zone()
            crop_screen = crop_image(screen, zone)
            if crop_screen is not None and crop_screen.size > 0:
                texts = wrapper.find_all_text(crop_screen)
                wrapper.log_info(f"is_heart_timer_visible OCR detected: {texts}")
                for text in texts:
                    if re.search(r"\d{1,2}:\d{2}", text):
                        return True
            sleep(0.5)
        return False

    def tap_refill(self) -> bool:
        return self.tap(self.btn_refill)

    def tap_buy_heart(self) -> bool:
        return self.tap(self.btn_buy_heart)

    def tap_add_heart(self) -> bool:
        return self.tap(self.btn_add_heart)

    def wait_for_heart_count(self, expected: int, timeout: int = 30) -> bool:
        """Poll until the heart count label matches expected value using OCR."""
        start = time.time()
        while time.time() - start < timeout:
            if self.get_heart_count_via_ocr() == expected:
                return True
            sleep(1)
        return False

    def get_heart_count_via_ocr(self) -> int:
        """Read the current heart count from the top bar using OCR. Returns -1 on failure."""
        from pixon.pages.home_page import HomePage

        home = HomePage()
        if not home.is_at_home():
            wrapper.log_error(
                "get_heart_count_via_ocr: not on homepage, attempting to go home"
            )
            home.go_home()
        screen = G.DEVICE.snapshot()
        from airtest.aircv import crop_image
        import re

        zone = self.get_heart_icon_zone()
        crop_screen = crop_image(screen, zone)
        if crop_screen is None or crop_screen.size == 0:
            return -1
        texts = wrapper.find_all_text(crop_screen)
        for text in texts:
            digits = re.findall(r"\d+", text)
            if digits:
                try:
                    val = int(digits[0])
                    if 0 <= val <= 5:
                        return val
                except ValueError:
                    pass
        return -1

    def get_heart_timer_str_via_ocr(self) -> str:
        """Read the heart refill timer/status text next to the heart icon using OCR."""
        from pixon.pages.home_page import HomePage

        home = HomePage()
        if not home.is_at_home():
            wrapper.log_error(
                "get_heart_timer_str_via_ocr: not on homepage, attempting to go home"
            )
            home.go_home()
        screen = G.DEVICE.snapshot()
        from airtest.aircv import crop_image

        zone = self.get_heart_timer_zone()
        crop_screen = crop_image(screen, zone)
        if crop_screen is None or crop_screen.size == 0:
            return ""
        texts = wrapper.find_all_text(crop_screen)
        for text in texts:
            cleaned = text.strip()
            if cleaned:
                return cleaned
        return ""

    def parse_timer_to_seconds(self, timer_str: str) -> int:
        """Parse timer string like '19:59' or '01:19:59' into total seconds."""
        # Replace common OCR misread punctuation with colon
        cleaned = timer_str.replace(".", ":").replace(",", ":").replace(";", ":")
        cleaned = "".join(c for c in cleaned if c.isdigit() or c == ":")
        parts = [p for p in cleaned.split(":") if p]
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        raise ValueError(f"Could not parse timer string: {timer_str!r} (cleaned: {cleaned!r})")

    def verify_heart_refill_timer(self) -> None:
        """Verify the heart refill timer status.

        - If current heart count is < 5: verifies that the timer is counting (format MM:SS).
        - If current heart count is >= 5: verifies that the timer text shows "Full".
        """
        import re

        heart_count = self.get_heart_count_via_ocr()
        timer_str = self.get_heart_timer_str_via_ocr()
        wrapper.log_info(
            f"verify_heart_refill_timer: heart={heart_count}, timer={timer_str!r}"
        )

        if heart_count == -1:
            wrapper.log_warning(
                "verify_heart_refill_timer: Could not read heart count via OCR."
            )
            return

        if heart_count < 5:
            if not re.match(r"^\d{1,2}:\d{2}$", timer_str):
                raise AssertionError(
                    f"Expected refill timer format MM:SS when heart count={heart_count} < 5, got {timer_str!r}"
                )
        else:
            if timer_str.lower() != "full":
                raise AssertionError(
                    f"Expected refill status 'Full' when heart count={heart_count} >= 5, got {timer_str!r}"
                )
