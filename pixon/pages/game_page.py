import re
import random
import time
import cv2
import numpy as np
from pixon.common import wrappers as wrapper
from pixon.common.adb_utils import set_autoplay, set_param
from airtest.core.api import sleep
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from pixon.common.test_flow import close_all_popups


class GamePage(BasePage):
    booster = [
        get_template("extend_play/btn_booster_1.png", (-0.218, 0.744)),
        get_template("extend_play/btn_booster_2.png", (-0.01, 0.74)),
        get_template("extend_play/btn_booster_3.png", (0.218, 0.744)),
        get_template("extend_play/btn_booster_4.png", (0.107, -0.61)),
    ]
    title_booster = [
        get_template("extend_play/title_booster_1.png", (0.007, -0.556)),
        get_template("extend_play/title_booster_2.png", (0.007, -0.554)),
        get_template("extend_play/title_booster_3.png", (0.007, -0.552)),
        get_template("extend_play/title_booster_4.png", (0.003, -0.557)),
    ]
    pay_coin = [
        get_template("extend_play/cost_booster_1.png", (0.172, 0.072)),
        get_template("extend_play/cost_booster_2.png", (0.171, 0.069)),
        get_template("extend_play/cost_booster_3.png", (0.170, 0.066)),
        get_template("extend_play/cost_booster_4.png", (0.176, 0.075)),
    ]
    btn_break = get_template("system_function/btn_break.png", (0.001, 0.532))
    btn_try_again = get_template("system_function/btn_try_again.png", (0.007, 0.072))
    btn_start = get_template("system_function/btn_start.png", (0.001, 0.546))
    label_choose_piece = get_template("extend_play/label_choose_piece.png", (0.00, 0.32))

    BOOSTER_INDEX = {
        "drill": 0,
        "hammer": 1,
        "magnet": 2,
    }
    COST_PER_BOOSTER = 100
    DRILL_PER_LEVEL = 2
    MAGNET_AUTOPLAY_SECONDS = 5
    ADVANCE_POLL_INTERVAL = 2
    ADVANCE_MAX_POLLS = 30
    ADVANCE_MAX_SECONDS = 60
    BOOSTER_ACTIVATE_RETRIES = 3

    @property
    def CENTER(self):
        w, h = self.get_screen_size()
        return (w // 2, h // 2)

    @property
    def RANDOM_BOARD_POINT(self):
        w, h = self.get_screen_size()
        return (random.randint(int(w * 0.3), int(w * 0.7)), random.randint(int(h * 0.45), int(h * 0.65)))

    @property
    def LEVEL_AREA(self):
        w, h = self.get_screen_size()
        return (0, 0, w, int(120 * h / 1280))

    def _parse_level_from_texts(self, texts):
        for t in texts:
            m = re.search(r"(?:level|lv)[^\d]*(\d+)", t, re.IGNORECASE)
            if m:
                return int(m.group(1))
            m2 = re.fullmatch(r"\d{1,4}", t.strip())
            if m2:
                val = int(m2.group())
                if 1 <= val <= 999:
                    return val

        for t in texts:
            m = re.fullmatch(r"\d{1,2}", t.strip())
            if m:
                val = int(m.group())
                if 1 <= val <= 999:
                    return val

        for t in texts:
            m = re.fullmatch(r"\d{3}", t.strip())
            if m:
                wrapper.log_info(
                    f"Detected 3-digit number{m.group()}, maybe OCR error"
                )
                return int(m.group())
        return None

    @wrapper.retry(times=5, delay=0.3, exceptions=(RuntimeError,), stable_retry=True)
    def _attempt_get_level(self) -> int | None:
        screen = wrapper.get_screen()
        if screen is None:
            wrapper.log_info("get_current_level: screen unavailable this attempt")
            return None

        x1, y1, x2, y2 = self.LEVEL_AREA
        strip = screen[y1:y2, x1:x2]
        texts = wrapper.find_all_text(strip)
        result = self._parse_level_from_texts(texts)
        if result is not None:
            return result
        try:
            bbox = wrapper.detect_level_badge(strip)
            if bbox is not None:
                badge_level = wrapper.read_level_from_badge(strip, bbox)
                if badge_level is not None:
                    if 0 <= badge_level <= 999:
                        return badge_level
        except Exception as e:
            wrapper.log_info(f"get_current_level: badge fallback raised {e!r}")

        return None

    def get_current_level(self) -> int:
        result = self._attempt_get_level()
        if result is not None:
            return result
        raise RuntimeError(
            "get_current_level: failed after all attempts, unable to detect level"
        )

    def activate_boosters(self) -> None:
        for i in range(len(self.booster)):
            if self.wait_for_element(self.booster[i], timeout=1.5):
                self.tap(self.booster[i])
                if self.wait_for_element(self.title_booster[i], timeout=1.5):
                    self.tap(self.pay_coin[i])
                    sleep(0.75)
                    self.tap(self.RANDOM_BOARD_POINT)
                    sleep(0.5)
                else:
                    self.tap(self.RANDOM_BOARD_POINT)
                    sleep(0.25)
            else:
                wrapper.log_info(f"Booster {i + 1} not found on screen")

    def _activate_single_booster(self, index: int) -> None:
        if self.wait_for_element(self.booster[index], timeout=1.5):
            self.tap(self.booster[index])
            sleep(0.5)
            if self.wait_for_element(self.title_booster[index], timeout=1.5):
                self.tap(self.pay_coin[index])
                sleep(0.25)
                self.tap(self.RANDOM_BOARD_POINT)
                sleep(0.25)
            else:
                self.tap(self.RANDOM_BOARD_POINT)
                sleep(0.25)
        else:
            raise wrapper.StepError(f"Booster {index + 1} not found on screen")

    def _activate_with_retry(self, index: int) -> bool:
        for attempt in range(self.BOOSTER_ACTIVATE_RETRIES):
            try:
                self._activate_single_booster(index)
                return True
            except wrapper.StepError:
                if attempt < self.BOOSTER_ACTIVATE_RETRIES - 1:
                    wrapper.log_warning(f"Booster {index + 1} not found (attempt {attempt+1}). Closing popups and retrying...")
                    if not hasattr(self, "_home_page_instance"):
                        self._home_page_instance = HomePage()
                    close_all_popups(self._home_page_instance, repeat=1)
                    sleep(1)
                else:
                    # log_info, not log_error: log_error always raises, which would
                    # escape this loop and abort the whole mission. Callers
                    # (_use_booster_with_retry) rely on the bool return to absorb
                    # transient misses within their own retry budget.
                    wrapper.log_info(f"Booster {index + 1} not found on screen after {self.BOOSTER_ACTIVATE_RETRIES} attempts")
        return False

    def _use_hammer_once(self) -> bool:
        index = self.BOOSTER_INDEX["hammer"]
        
        banner_appeared = False
        
        # Check if banner is already visible
        if self.wait_for_element(self.label_choose_piece, timeout=1.0):
            banner_appeared = True
        else:
            # Must tap btn_booster_2 first, then check banner. If not show, tap again.
            for _ in range(3):
                if not self.wait_for_element(self.booster[index], timeout=1.5):
                    return False
                    
                self.tap(self.booster[index])
                sleep(1.5)
                
                if self.wait_for_element(self.label_choose_piece, timeout=1.5):
                    banner_appeared = True
                    break
                
        if not banner_appeared:
            wrapper.log_info("_use_hammer_once: banner failed to appear after tapping booster")
            return False
            
        # Then tap the zone to use, then recheck did the banner disappear
        for attempt in range(10):
            # Swipe left or right to move the board and find pieces
            self.swipe(random.choice(("left", "right")))
            sleep(0.5)
            
            self.tap(self.CENTER)
            sleep(1.5)  # Wait for break animation
            
            # Recheck did the banner disappear
            if not self.wait_for_element(self.label_choose_piece, timeout=1.0):
                # If disappear then end the loop -> finish 1 loop
                return True
            
            wrapper.log_info(f"_use_hammer_once: hammer missed (banner still visible), retrying tap (attempt {attempt+1})")
            
        return False

    def _use_booster_with_retry(self, count: int, action_callback, booster_name: str) -> int:
        used = 0
        attempts = 0
        max_attempts = count * self.BOOSTER_ACTIVATE_RETRIES

        while used < count and attempts < max_attempts:
            attempts += 1
            if action_callback():
                used += 1
            else:
                wrapper.log_info(f"use_{booster_name}: booster failed or not found, retrying...")
                sleep(1)
                
        if used < count:
            wrapper.log_info(f"use_{booster_name}: only used {used}/{count}")
            
        return used

    def use_drill(self, count: int) -> None:
        index = self.BOOSTER_INDEX["drill"]
        used = 0
        while used < count:
            batch_target = min(self.DRILL_PER_LEVEL, count - used)
            batch_used = self._use_booster_with_retry(batch_target, lambda: self._activate_with_retry(index), "drill")
            used += batch_used
            
            if batch_used < batch_target:
                break
                
            if used < count:
                self._advance_one_level()

    def use_hammer(self, count: int) -> None:
        self._use_booster_with_retry(count, self._use_hammer_once, "hammer")

    def get_progress_zone_crop(self):
        screen = wrapper.get_screen()
        if screen is None:
            return None
        
        h, w = screen.shape[:2]
        # Crop the region of the 5 progress circles
        y1, y2 = int(h * 0.22), int(h * 0.25)
        x1, x2 = int(w * 0.25), int(w * 0.75)
        
        return screen[y1:y2, x1:x2].copy()

    def wait_for_color_trigger(self, timeout_seconds: float) -> None:
        initial_crop = self.get_progress_zone_crop()
        if initial_crop is None:
            wrapper.log_info("wait_for_color_trigger: Cannot get initial crop, aborting")
            return
            
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout_seconds:
                set_autoplay(True)
                set_param("playspeed", 1)
                sleep(0.5)
                
                # Stop autoplay and check in middle
                set_autoplay(False)
                set_param("playspeed", 6)
                sleep(0.5)
                
                current_crop = self.get_progress_zone_crop()
                if current_crop is not None:
                    # Check for significant change in the zone
                    diff = cv2.absdiff(initial_crop, current_crop)
                    mean_diff = np.mean(diff)
                    if mean_diff > 5.0:  # Threshold for noticeable change
                        wrapper.log_info(f"wait_for_color_trigger: Color trigger detected! (diff: {mean_diff:.2f})")
                        break
        finally:
            set_autoplay(False)

    def use_magnet(self, count: int) -> None:
        index = self.BOOSTER_INDEX["magnet"]
        def _magnet_action():
            self.wait_for_color_trigger(self.MAGNET_AUTOPLAY_SECONDS)
            return self._activate_with_retry(index)
            
        self._use_booster_with_retry(count, _magnet_action, "magnet")

    def _advance_one_level(self) -> None:
        """Autoplay one level forward, then stop. Best-effort.

        Reads the current level, enables autoplay, polls until the level
        increments (or the poll/time budget is spent), then disables autoplay.
        get_current_level may raise RuntimeError on OCR failure; treat that as
        "no reading this tick" and keep polling. autoplay is ALWAYS restored via
        finally so an unexpected (non-RuntimeError) error never leaves it
        globally enabled. A wall-clock deadline bounds the pathological
        screen-unavailable case where each read can burn the full retry budget.
        """
        try:
            start = self.get_current_level()
        except RuntimeError:
            start = None
        advanced = False
        deadline = time.monotonic() + self.ADVANCE_MAX_SECONDS
        try:
            from pixon.common.adb_utils import set_level_result
            set_level_result(True)
            set_autoplay(True)
            for _ in range(self.ADVANCE_MAX_POLLS):
                if time.monotonic() >= deadline:
                    break
                sleep(self.ADVANCE_POLL_INTERVAL)
                try:
                    current = self.get_current_level()
                except RuntimeError:
                    continue
                if start is None:
                    start = current
                    continue
                if current > start:
                    advanced = True
                    break
        finally:
            set_autoplay(False)
        if not advanced:
            wrapper.log_info(
                "drill advance: level did not increment within poll budget"
            )

    def use_booster(self, booster_type: str, count: int) -> None:
        if booster_type in ("", "any"):
            for _ in range(count):
                self.activate_boosters()
            return
        if booster_type == "drill":
            self.use_drill(count)
            return
        if booster_type == "hammer":
            self.use_hammer(count)
            return
        if booster_type == "magnet":
            self.use_magnet(count)
            return
        wrapper.log_warning(f"use_booster: unknown booster type '{booster_type}'")

    def spend_coins(self, amount: int) -> None:
        times = (amount + self.COST_PER_BOOSTER - 1) // self.COST_PER_BOOSTER
        if times <= 0:
            times = 1
        self.use_booster("any", times)
