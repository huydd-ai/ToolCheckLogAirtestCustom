# pages/magic_bean_page.py
from pixon.pages.base_page import BasePage, get_template
from airtest.core.api import sleep
import os
from typing import Dict, Optional, Tuple


class MagicBeanPage(BasePage):
    DEFAULT_PROFILE = {
        "fakeads": True,
        "heart": 5,
        "coin": 10000,
        "playspeed": 6,
        "server_sync": False,
        "clear_data": True,  # fresh start: wipe old data, no need to check prior state
    }

    MAGICBEAN_UNLOCK_LEVEL = 33

    icon = get_template("magic_bean/icon.png", (-0.4, 0.022))
    # icon_1 now reuses the same (new) icon capture + record_pos as icon
    icon_1 = icon
    popup_start_event = get_template("magic_bean/popup_start_event.png", (-0.015, -0.113))
    btn_start = get_template("magic_bean/btn_start.png", (-0.008, 0.557))
    # ponytail: reuse shared tap_to_continue image, same as LavaQuest overlay
    tap_to_continue = get_template("tap_to_continue.png", (-0.004, 0.55), threshold=0.85)
    event_board = get_template("magic_bean/event_board.png", (-0.001, -0.589))
    chest_locked = get_template("magic_bean/chest_locked.png", (-0.093, -0.314))
    chest_unlocked = get_template("magic_bean/chest_unlocked.png", (-0.122, 0.286))
    chest_claimed = get_template("magic_bean/chest_claimed.png", (-0.103, 0.304))
    lose_popup_1 = get_template("magic_bean/lose_popup_1.png", (-0.001, -0.228))
    lose_popup_2 = get_template("magic_bean/lose_popup_2.png", (0.004, -0.296))
    lose_popup_3 = get_template("magic_bean/lose_popup_3.png", (0.008, -0.278))
    btn_try_again = get_template("magic_bean/btn_try_again.png", (0.003, 0.072))
    # shared close button, same path/pos as LavaQuest
    btn_close = get_template("system_function/btn_close.png", (0.365, -0.861))
    # no claim-all screen/button exists: after the event ends the normal event
    # board shows (no popup, no cue); claim = tap chest -> overlay ->
    # HomePage.tap_to_claim, same as any mid-event claim
    warning_popup = get_template("magic_bean/warning_popup.png", (0.001, -0.121))

    def is_event_icon_visible(self, timeout: float = 2.5) -> bool:
        return self.wait_for_element([self.icon, self.icon_1], timeout=timeout)

    def _find_event_icon(self, timeout: float = 5):
        """Search both icon variants, return the matched coords or None.

        Polls the two captures alternately within one deadline (not a full
        timeout per variant) and returns the exact match position, so the
        tap happens on the found coords -- no second template search that
        can miss after the detection matched.
        """
        import time
        from pixon.common import wrappers as wrapper
        deadline = time.time() + timeout
        while True:
            for icon in (self.icon, self.icon_1):
                coord = wrapper.partial_search(icon)
                if coord:
                    return coord
            if time.time() >= deadline:
                return None
            sleep(0.5)

    def tap_event_icon(self, timeout: float = 5) -> bool:
        """Tap the Magic Bean home icon, whichever captured variant matches."""
        coord = self._find_event_icon(timeout=timeout)
        if not coord:
            return False
        return self.tap(coord)

    def dismiss_tutorial_overlay(self, max_taps: int = 5, timeout: float = 3) -> int:
        """Tap through the multi-step 'Tap to continue' tutorial overlay.

        The overlay auto-appears on first unlock and is NOT a popup --
        close_all_popups does not clear it. Returns the number of taps
        performed (0 = no overlay was shown).
        """
        taps = 0
        while taps < max_taps and self.wait_for_element(self.tap_to_continue, timeout=timeout):
            self.tap(self.tap_to_continue)
            taps += 1
            sleep(1)
        return taps

    def verify_unlock_flow(self, home_page, timeout: float = 5) -> bool:
        """Handle the lv33 unlock popup storm end-to-end.

        Observed behavior: at lv33 many popups appear; one is the Magic Bean
        tutorial overlay (popup_start_event, shown with a tap_to_continue
        prompt). Do NOT tap-through the overlay -- tapping tap_to_continue once
        closes it and that action already STARTS the event. After closing, the
        event is running, so tapping the Magic Bean icon opens the progress
        board (event_board) directly.

        Flow: detect the tutorial overlay -> tap tap_to_continue to close it
        (event starts) -> close remaining popups -> tap the icon -> the
        progress board must be visible -> close it.

        Returns True when the tutorial overlay fired and the flow verified,
        False when it did not appear (not first unlock / already started /
        below threshold) -- in that case only close_all_popups runs.
        Raises StepError (via log_error) on any must-pass check failing.
        """
        from pixon.common import test_flow
        from pixon.common import wrappers as wrapper

        # tutorial overlay = popup_start_event; no overlay -> nothing to start
        if not self.wait_for_element(self.popup_start_event, timeout=timeout):
            test_flow.close_all_popups(home_page)
            return False
        # tapping tap_to_continue closes the overlay and STARTS Magic Bean
        self.tap(self.tap_to_continue)
        sleep(2)
        test_flow.close_all_popups(home_page)
        # event already started -> icon opens the progress board directly
        if not self.open_event_popup(timeout=timeout):
            wrapper.log_error(
                "Magic Bean unlock flow: icon tap did not open progress board after start"
            )
        self.tap(self.btn_close)
        test_flow.close_all_popups(home_page)
        return True

    def is_chest_locked(self, timeout: float = 2.5) -> bool:
        return self.wait_for_element(self.chest_locked, timeout=timeout)

    def is_chest_unlocked(self, timeout: float = 2.5) -> bool:
        return self.wait_for_element(self.chest_unlocked, timeout=timeout)

    def is_chest_claimed(self, timeout: float = 2.5) -> bool:
        return self.wait_for_element(self.chest_claimed, timeout=timeout)

    def is_warning_popup_visible(self, timeout: float = 2.5) -> bool:
        return self.wait_for_element(self.warning_popup, timeout=timeout)

    def open_event_popup(self, timeout: float = 5) -> bool:
        """Tap Magic Bean icon on home → wait for event board/popup to appear.

        Detects either icon variant and taps the matched coords; retries the
        tap once if the board/popup does not come up. If the first-open
        tutorial overlay fires instead of the board, taps through it and
        retries.
        """
        for _ in range(2):
            coord = self._find_event_icon(timeout=timeout)
            if not coord:
                return False
            self.tap(coord)
            sleep(1)
            if self.wait_for_element(self.event_board, timeout=timeout):
                return True
            if self.wait_for_element(self.popup_start_event, timeout=0.5):
                return True
            # first open may show the tutorial overlay instead of the board
            self.dismiss_tutorial_overlay(timeout=1.5)
        return False

    def claim_chest(self) -> bool:
        """Tap an unlocked chest -> reward overlay -> tap_to_claim to collect it."""
        if not self.wait_for_element(self.chest_unlocked, timeout=5):
            return False
        self.tap(self.chest_unlocked)
        sleep(2)
        from pixon.pages.home_page import HomePage
        if self.wait_for_element(HomePage.tap_to_claim, timeout=5):
            self.tap(HomePage.tap_to_claim)
            sleep(0.5)
        if self.wait_for_element(self.btn_close, timeout=3):
            self.tap(self.btn_close)
        return True

    def validate_reward_against_db(
        self,
        milestone: int,
        expected_coins: Optional[int] = None,
        expected_items: Optional[Dict[str, int]] = None,
        db_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validate a milestone reward entry against magicbean_reward_table.json.

        Looks up the milestone by number and compares provided expected
        values (only the fields the caller supplies are checked).
        Returns (ok, reason). Caller decides warn-vs-raise.
        """
        import json
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "Test", "MagicBean", "magicbean_reward_table.json",
            )
        with open(os.path.abspath(db_path), "r", encoding="utf-8") as f:
            db = json.load(f).get("magic_bean_reward_table", {})
        entry = next((e for e in db.get("milestones", []) if e["milestone"] == milestone), None)
        if entry is None:
            return False, f"no db entry for milestone {milestone}"
        if expected_coins is not None and entry.get("coins") != expected_coins:
            return False, f"coins: expected {expected_coins}, db has {entry.get('coins')} for milestone {milestone}"
        if expected_items is not None and entry.get("items") != expected_items:
            return False, f"items: expected {expected_items}, db has {entry.get('items')} for milestone {milestone}"
        return True, "ok"

    def check_beanstalk_progress(self, expected_level: int) -> Optional[bool]:
        """
        Verify visually that the beanstalk progress has reached the given level.
        It uses OCR to find the level number, then checks for a bright green
        beanstalk just below that level's bounding box.

        Returns True/False for a measured result, None when the marker could
        not be located (OCR miss / bad ROI). Callers doing NEGATIVE checks
        must distinguish False (measured: not reached) from None (unknown) --
        treating None as "not reached" false-passes on any OCR hiccup.
        """
        import cv2
        import numpy as np
        from pixon.common.ocr import find_text_boxes
        from airtest.core.api import G
        from pixon.common import wrappers as wrapper
        
        screen = G.DEVICE.snapshot()
        # find_text_boxes matches substrings ("2" hits "x2", "10000", ...) --
        # keep only exact digit matches so we anchor on the level marker itself.
        target = str(expected_level)
        boxes = [b for b in find_text_boxes(screen, target) if b.text.strip() == target]
        if not boxes:
            wrapper.log_warning(f"Could not find level marker '{target}' on screen via OCR")
            return None
        if len(boxes) > 1:
            wrapper.log_warning(
                f"check_beanstalk_progress: {len(boxes)} exact '{target}' matches, using highest-confidence one"
            )
        x, y, w, h = max(boxes, key=lambda b: b.conf).bbox
        
        # Check a small ROI right below the marker for bright green.
        roi_y1 = min(y + h, screen.shape[0] - 1)
        roi_y2 = min(roi_y1 + 100, screen.shape[0])
        roi_x1 = max(0, x - 50)
        roi_x2 = min(x + w + 50, screen.shape[1])
        
        if roi_y2 <= roi_y1 or roi_x2 <= roi_x1:
            wrapper.log_warning("Invalid ROI for beanstalk check")
            return None
            
        roi = screen[roi_y1:roi_y2, roi_x1:roi_x2]
        if roi.ndim == 3 and roi.shape[2] == 4:
            roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)
            
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # Bright green color range
        lower_green = np.array([35, 100, 100])
        upper_green = np.array([85, 255, 255])
        
        mask = cv2.inRange(hsv_roi, lower_green, upper_green)
        green_ratio = np.sum(mask > 0) / (mask.shape[0] * mask.shape[1])
        
        wrapper.log_info(f"check_beanstalk_progress: found green ratio {green_ratio:.2f} at roi {roi_x1},{roi_y1} to {roi_x2},{roi_y2}")

        return bool(green_ratio > 0.05)


def demo() -> None:
    """Offline self-check for validate_reward_against_db (no device needed)."""
    import json
    import tempfile

    fixture = {
        "magic_bean_reward_table": {
            "milestones": [
                {"milestone": 1, "cumulative_wins": 2, "items": {"money": 20}, "coins": 20, "chest": "wood"},
                {"milestone": 2, "cumulative_wins": 5, "items": {"drill": 1}, "coins": 80, "chest": "wood"},
            ]
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(fixture, f)
        fixture_path = f.name

    # ponytail: bypass BasePage.__init__ (needs a device) — method uses no instance state
    page = object.__new__(MagicBeanPage)
    assert page.validate_reward_against_db(1, expected_coins=20, db_path=fixture_path)[0] is True
    assert page.validate_reward_against_db(2, expected_items={"drill": 1}, db_path=fixture_path)[0] is True
    assert page.validate_reward_against_db(1, expected_coins=999, db_path=fixture_path)[0] is False
    assert page.validate_reward_against_db(99, db_path=fixture_path)[0] is False  # no such milestone

    os.remove(fixture_path)
    print("validate_reward_against_db: all checks passed")

    # --- offline check for verify_unlock_flow orchestration (no device) ---
    import pixon.common.test_flow as tf
    import pixon.pages.magic_bean_page as mbp
    from pixon.common.logging_utils import StepError

    def make_wait(overlay_present):
        def _wait(tmpl, *a, **kw):
            if tmpl is MagicBeanPage.popup_start_event:
                calls.append("overlay_check")
                return overlay_present
            calls.append("other_check")
            return True
        return _wait

    calls = []
    flow = object.__new__(MagicBeanPage)
    # generic tap stub: records "tap" for both the tap_to_continue (close/start)
    # and the final btn_close tap
    flow.tap = lambda *a, **kw: (calls.append("tap"), True)[1]
    _orig_close = tf.close_all_popups
    _orig_sleep = mbp.sleep
    tf.close_all_popups = lambda home, **kw: calls.append("close_popups")
    mbp.sleep = lambda *a, **k: None
    try:
        # Case 1: overlay fires -> tap to close (starts event) -> close popups
        # -> icon opens progress board -> close
        flow.wait_for_element = make_wait(overlay_present=True)
        flow.open_event_popup = lambda **kw: (calls.append("icon_open"), True)[1]
        assert flow.verify_unlock_flow(home_page=object()) is True
        assert calls == [
            "overlay_check", "tap", "close_popups", "icon_open", "tap", "close_popups",
        ], calls

        # Case 2: no overlay -> just clean popups, no icon tap, returns False
        calls.clear()
        flow.wait_for_element = make_wait(overlay_present=False)
        assert flow.verify_unlock_flow(home_page=object()) is False
        assert calls == ["overlay_check", "close_popups"], calls

        # Case 3: overlay fired but icon does NOT open the board -> must raise
        # (log_error raises StepError)
        calls.clear()
        flow.wait_for_element = make_wait(overlay_present=True)
        flow.open_event_popup = lambda **kw: (calls.append("icon_open"), False)[1]
        raised = False
        try:
            flow.verify_unlock_flow(home_page=object())
        except StepError:
            raised = True
        assert raised, "verify_unlock_flow must raise StepError when icon does not open progress board"
    finally:
        tf.close_all_popups = _orig_close
        mbp.sleep = _orig_sleep
    print("verify_unlock_flow: all checks passed")


if __name__ == "__main__":
    demo()
