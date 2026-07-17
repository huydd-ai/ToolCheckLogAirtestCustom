from pixon.pages.base_page import BasePage, get_template
from airtest.aircv import crop_image
from airtest.core.api import sleep, touch
from pixon.common import wrappers as wrapper
import re
import os
import functools
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, Union, cast


@dataclass
class RewardRead:
    win_amount: int
    other_winners: int
    confidence: float   # coarse diagnostic: min line-conf in crop, NOT per-field
    raw: str
    ok: bool            # both fields parsed


@functools.lru_cache(maxsize=None)
def _load_reward_db_from_path(db_path: str) -> Dict[str, Any]:
    import json
    with open(db_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f).get("lava_quest_reward_db", {})
        return data


class LavaQuestPage(BasePage):
    DEFAULT_PROFILE = {
        "fakeads": True,
        "heart": 5,
        "coin": 10000,
        "playspeed": 6,
        "server_sync": False,
    }

    btn_start = get_template("lava_quest/btn_start.png", (0.0, 0.543))
    label_lavaquest = get_template("lava_quest/label_lavaquest.png", (0.015, -0.706))
    label_player_group_lavaquest = get_template("lava_quest/label_player_group_lavaquest.png", (0.003, -0.025))
    label_level_complete_lavaquest = get_template("lava_quest/label_level_complete_lavaquest.png", (-0.151, -0.625))
    label_players_number_count_lavaquest = get_template("lava_quest/label_players_number_count_lavaquest.png", (0.153, -0.624))
    label_time_count_down_lavaquest = get_template("lava_quest/label_time_count_down_lavaquest.png", (0.587, 0.202))
    label_win_lava_quest = get_template("lava_quest/label_win_lava_quest.png", (0.097, -0.046))

    # ponytail: aliases — tests reference these names; reuse existing images
    btn_lava_quest = get_template("home_page/btn_toy_adventure.png", (-0.397, -0.383))
    event_board = get_template("lava_quest/event_board.png", (0.0, -0.817))  # popup header / board identifier
    event_countdown = label_time_count_down_lavaquest
    claim_btn = get_template("system_function/btn_claim.png", (0.0, 0.3))
    btn_close = get_template("system_function/btn_close.png", (0.365, -0.861))
    # ponytail: reuse existing tap_to_continue image for LQ overlay
    tap_to_continue = get_template("tap_to_continue.png", (-0.004, 0.55), threshold=0.85)

    def open_lava_quest_popup(self, timeout: float = 5) -> bool:
        """Tap LQ icon on home → wait for popup board to appear."""
        if not self.wait_for_element(self.btn_lava_quest, timeout=timeout):
            return False
        self.tap(self.btn_lava_quest)
        sleep(1)
        return self.is_lava_quest_open(timeout=timeout)

    def handle_event_over_popup(self) -> None:
        """Dismiss 'event over' overlay if visible, otherwise no-op."""
        # ponytail: the event-over popup uses the same close button
        if self.wait_for_element(self.btn_close, timeout=3):
            self.tap(self.btn_close)
            sleep(0.5)

    def get_streak_count_via_ocr(self) -> int:
        """OCR-read the win streak number near the level complete label. Returns 0 on failure."""
        raw = self.check_level_text()
        digits = re.findall(r"\d+", raw)
        return int(digits[0]) if digits else 0

    def _parse_reward(self, raw: str, conf: float = 0.0) -> RewardRead:
        win_match = re.search(r"Win\D*(\d+)", raw, re.IGNORECASE)
        winners_match = re.search(r"(\d+)\s*other\s*winner", raw, re.IGNORECASE)
        win_amount = int(win_match.group(1)) if win_match else 0
        other_winners = int(winners_match.group(1)) if winners_match else 0
        ok = win_match is not None and winners_match is not None
        return RewardRead(win_amount, other_winners, conf, raw, ok)

    def get_reward_and_winners_via_ocr(self) -> RewardRead:
        """OCR-read win amount + other-winner count from the claim screen.

        Re-OCRs a wider crop once if the primary regex misses (parse failure,
        not empty text — the anchor text is almost always inside the crop).
        Returns a RewardRead (ok=False if both attempts fail to parse).
        """
        raw, conf = cast(Tuple[str, float], self._get_text_near_template(self.label_win_lava_quest, expand_w=300, expand_h=200, with_conf=True))
        result = self._parse_reward(raw, conf)
        if not result.ok:   # got text but regex missed → widen crop, re-parse
            raw2, conf2 = cast(Tuple[str, float], self._get_text_near_template(self.label_win_lava_quest, expand_w=420, expand_h=300, with_conf=True))
            retry = self._parse_reward(raw2, conf2)
            if retry.ok:
                result = retry
        wrapper.log_info(f"reward OCR: {result}")
        return result

    def validate_reward_against_db(self, win_amount: int, bot_remaining: int, level: int = 7, db_path: Optional[str] = None) -> Tuple[bool, str]:
        """Validate OCR'd (win_amount, bot_remaining) against reward_table.json.

        Returns (ok, reason). Caller decides warn-vs-raise.
        """
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "Test", "LavaQuest", "reward_table.json",
            )
        db = _load_reward_db_from_path(os.path.abspath(db_path))
        entry = next((e for e in db.get("levels", []) if e["level"] == level), None)
        if entry is None:
            return False, f"no db entry for level {level}"
        if not (entry["bot_min"] <= bot_remaining <= entry["bot_max"]):
            return False, (f"bot_remaining {bot_remaining} outside level-{level} "
                           f"range {entry['bot_min']}-{entry['bot_max']}")
        expected = round(db["total_reward"] / (bot_remaining + 1))
        if win_amount != expected:
            return False, f"win {win_amount} != expected {expected} (5000/{bot_remaining+1})"
        return True, "ok"

    def claim_reward(self) -> bool:
        """Tap claim button and confirm reward collection."""
        if not self.wait_for_element(self.claim_btn, timeout=5):
            return False
        self.tap(self.claim_btn)
        sleep(3)
        # If we are on the Win screen, we need to tap "TAP TO CLAIM"
        from pixon.pages.home_page import HomePage
        tap_to_claim_btn = HomePage.tap_to_claim
        if self.wait_for_element(tap_to_claim_btn, timeout=5):
            self.tap(tap_to_claim_btn)
            sleep(3)
        # ponytail: dismiss any reward confirmation popup
        if self.wait_for_element(self.btn_close, timeout=3):
            self.tap(self.btn_close)
        return True

    def _get_text_near_template(self, template: Any, expand_w: int = 50, expand_h: int = 30, offset_x: int = 0, offset_y: int = 0, with_conf: bool = False) -> Union[str, Tuple[str, float]]:
        pos = wrapper.wait_exists_pos(template, timeout=2.5)
        if pos is None:
            return ("", 0.0) if with_conf else ""
        screen = wrapper.get_screen()
        x, y = pos
        w_factor = screen.shape[1] / 720.0
        h_factor = screen.shape[0] / 1280.0
        cx = x + int(offset_x * w_factor)
        cy = y + int(offset_y * h_factor)
        x1 = max(0, cx - int(expand_w * w_factor))
        y1 = max(0, cy - int(expand_h * h_factor))
        x2 = min(screen.shape[1], cx + int(expand_w * w_factor))
        y2 = min(screen.shape[0], cy + int(expand_h * h_factor))
        cropped = crop_image(screen, (int(x1), int(y1), int(x2), int(y2)))
        lines = wrapper.find_all_text_with_conf(cropped)
        text = " ".join(line.text for line in lines) if lines else ""
        if with_conf:
            conf = min((line.conf for line in lines), default=0.0)
            return text, conf
        return text

    def check_level_text(self) -> str:
        return cast(str, self._get_text_near_template(self.label_level_complete_lavaquest, expand_w=100, expand_h=60))

    def check_players_text(self) -> str:
        anchor = self.label_players_number_count_lavaquest
        if not wrapper.wait_exists(anchor, timeout=1.0):
            # Fallback to level complete label with offset
            return cast(str, self._get_text_near_template(self.label_level_complete_lavaquest, expand_w=100, expand_h=30, offset_x=220))
        return cast(str, self._get_text_near_template(anchor, expand_w=100, expand_h=60))

    def check_timer_text(self) -> str:
        return cast(str, self._get_text_near_template(self.label_time_count_down_lavaquest, expand_w=150, expand_h=50))

    def is_timer_running_in_zone(self, timeout: float = 5) -> bool:
        """Scan a fixed OCR zone for the countdown timer (e.g. 23h:58m)."""
        # Timer zone approx coordinates on 720x1280 screen: [x_min, y_min, x_max, y_max]
        timer_zone = [230, 200, 490, 280]
        if self.wait_for_text("h", area=timer_zone, timeout=timeout):
            return True
        if self.wait_for_text("m", area=timer_zone, timeout=1):
            return True
        return False

    def is_lava_quest_open(self, timeout: float = 2.5) -> bool:
        # It's open if we see the normal title, the level complete label, the claim button, or the cooldown timer
        if self.wait_for_element(self.label_lavaquest, timeout=timeout):
            return True
        if self.wait_for_element(self.label_level_complete_lavaquest, timeout=0.5):
            return True
        if self.wait_for_element(self.claim_btn, timeout=0.5):
            return True
        if self.wait_for_element(self.label_time_count_down_lavaquest, timeout=0.5):
            return True
        return False

    def tap_btn_start(self) -> bool:
        """Tap start button with retries in case of flakiness/lag."""
        for attempt in range(3):
            if not self.wait_for_element(self.btn_start, timeout=2):
                if self.is_player_group_visible(timeout=2):
                    return True
                continue
            self.tap(self.btn_start)
            sleep(2)
            if not self.wait_for_element(self.btn_start, timeout=2):
                return True
        return False

    def is_player_group_visible(self, timeout: float = 2.5) -> bool:
        return bool(self.wait_for_element(self.label_player_group_lavaquest, timeout=timeout))

    def is_level_complete_visible(self, timeout: float = 2.5) -> bool:
        return bool(self.wait_for_element(self.label_level_complete_lavaquest, timeout=timeout))

    def is_players_number_count_visible(self, timeout: float = 2.5) -> bool:
        return bool(self.wait_for_element(self.label_players_number_count_lavaquest, timeout=timeout))

    def is_time_count_down_visible(self, timeout: float = 2.5) -> bool:
        return bool(self.wait_for_element(self.label_time_count_down_lavaquest, timeout=timeout))

    def is_win_visible(self, timeout: float = 2.5) -> bool:
        return bool(self.wait_for_element(self.label_win_lava_quest, timeout=timeout))

    # ponytail: shared helpers — avoid duplicating first-time flow and win loop in every test

    def complete_first_time_flow(self) -> None:
        """Handle find-players overlay + 3-tap tutorial on first LQ entry.

        Call after tap_btn_start() on a fresh install (clear_data=True).
        """
        # 4. Wait for 3s label_player_group_lavaquest.png (matchmaking)
        sleep(3)
        if not self.wait_for_element(self.label_player_group_lavaquest, timeout=10):
            raise AssertionError("Matchmaking player group did not appear")

        # 5. Tap tap_to_continue
        if self.wait_for_element(self.tap_to_continue, timeout=5):
            self.tap(self.tap_to_continue)
        sleep(1)

        # 6. Tutorial: tap center of 720x1280 screen 3 times, 1s break each
        for _ in range(3):
            touch((360, 640))
            sleep(1)

        # 7. Check label_level_complete_lavaquest and label_players_number_count_lavaquest
        if not self.wait_for_element(self.label_level_complete_lavaquest, timeout=5):
            raise AssertionError("Level complete (0/7) label not visible")
        if not self.wait_for_element(self.label_players_number_count_lavaquest, timeout=5):
            raise AssertionError("Player group (100/100) label not visible")

        # OCR verify player count is 100
        players_text = self.check_players_text()
        match = re.search(r'(\d+)', players_text)
        if match:
            players = int(match.group(1))
            if players != 100:
                raise AssertionError(f"Expected 100 players after matchmaking, but got {players} (from '{players_text}')")
        else:
            raise AssertionError(f"Could not parse player count from OCR text '{players_text}'")

    def play_and_win_levels(self, home_page: Any, count: int = 7) -> None:
        """Tap play, win `count` levels.

        Expects to be on the home screen with LQ active.
        """
        from pixon.common.adb_utils import set_param, set_autoplay

        # First level: tap play, ensure autoplay is disabled so it doesn't fail
        from pixon.common.test_flow import close_all_popups
        close_all_popups(home_page)
        home_page.tap(home_page.btn_main_play)
        sleep(4)
        set_autoplay(False)

        for i in range(1, count + 1):
            sleep(3)
            set_param("set_level_win", True)
            close_all_popups(home_page)
            sleep(2)
            home_page.tap(home_page.btn_next)
            sleep(2)

            # After the final win the "You Win" overlay appears instead of the
            # event_board — skip board checks and leave the overlay for the
            # caller (tc06) to verify and dismiss.
            if i == count:
                wrapper.log_info(f"Final win {i}/{count} done — skipping event_board check (You Win overlay expected)")
                break

            if not self.wait_for_element(self.event_board, timeout=10):
                raise AssertionError(f"Lava Quest event board did not appear after winning level {i}/{count}")

            sleep(1)
            expected_streak = i
            streak, level_num = -1, -1
            for attempt in range(1, 4):
                streak = self.get_streak_count_via_ocr()
                lvl_text = self.check_level_text()
                lvl_match = re.search(r"(\d+)\s*/\s*7", lvl_text)
                level_num = int(lvl_match.group(1)) if lvl_match else -1
                wrapper.log_info(
                    f"Lava Quest OCR attempt {attempt}: streak={streak}/{count}, level={level_num}/7 "
                    f"(expected {expected_streak})"
                )
                if streak == expected_streak and level_num == expected_streak:
                    break
                sleep(1.5)

            if streak != expected_streak:
                wrapper.log_error(f"Expected streak {expected_streak}, but OCR read {streak}")
            if level_num != expected_streak:
                wrapper.log_error(f"Expected level {expected_streak}/7, but OCR read {level_num}/7")

            players_text = self.check_players_text()
            match = re.search(r'(\d+)\s*/\s*100', players_text)
            if match:
                players = int(match.group(1))
                expected_ranges = {
                    0: (90, 100),
                    1: (70, 90),
                    2: (50, 70),
                    3: (35, 55),
                    4: (25, 40),
                    5: (20, 30),
                    6: (15, 25),
                }
                expected_min, expected_max = expected_ranges.get(expected_streak, (0, 100))
                wrapper.log_info(f"Players remaining after {i} win(s): {players}/100 (expected {expected_min}-{expected_max})")
                if not (expected_min <= players <= expected_max):
                    wrapper.log_error(f"Expected players between {expected_min}-{expected_max}, but got {players}")
            else:
                wrapper.log_error(f"Could not parse player count (expected X/100) from '{players_text}'")
            
            if home_page.wait_for_element(home_page.btn_close, timeout=5):
                home_page.tap(home_page.btn_close)
                sleep(1)
            else:
                wrapper.log_error("Could not find btn_close to dismiss Lava Quest progress popup")
        
            # Start the next level if we have more to play
            if i < count:
                from pixon.common.test_flow import close_all_popups
                close_all_popups(home_page)
                home_page.tap(home_page.btn_main_play)
                sleep(4)
                set_autoplay(False)

        sleep(2)

    def initialize_quest(self, home_page: Any) -> None:
        """Helper to open LQ, start it, do first-time tutorial, and close popup."""
        from pixon.common.test_flow import run_step
        
        # 1-2. Tap icon and check label_lavaquest
        if not self.wait_for_element(self.btn_lava_quest, timeout=10):
            raise AssertionError("Lava Quest icon did NOT appear")
        self.tap(self.btn_lava_quest)
        if not self.wait_for_element(self.label_lavaquest, timeout=15):
            raise AssertionError("Lava Quest popup did not open initially")
            
        # 3. Tap btn_start
        run_step("tap btn_start", self.tap_btn_start)
        
        # 4-7. Complete first-time flow
        run_step("complete first-time flow", self.complete_first_time_flow)
        
        # 8. Tap btn_close
        home_page.tap(home_page.btn_close)
        sleep(2)


def demo() -> None:
    """Offline self-check for validate_reward_against_db and _parse_reward (no device needed)."""
    # ponytail: bypass BasePage.__init__ (needs a device) — methods use no instance state
    page = object.__new__(LavaQuestPage)
    assert page.validate_reward_against_db(57, 87, level=1)[0] is True
    assert page.validate_reward_against_db(500, 9, level=7)[0] is True
    assert page.validate_reward_against_db(56, 87, level=1)[0] is False   # floor would give 56
    assert page.validate_reward_against_db(500, 99, level=7)[0] is False  # bot out of lv7 range

    # _parse_reward is pure (string in, struct out)
    r = page._parse_reward("Win 500 9 other winners", 0.9)
    assert r.win_amount == 500 and r.other_winners == 9 and r.ok is True
    r = page._parse_reward("Score 500 9 other winners", 0.9)   # no "Win" → partial parse
    assert r.ok is False and r.win_amount == 0 and r.other_winners == 9
    r = page._parse_reward("Win 500", 0.9)                      # no winners → partial parse
    assert r.ok is False and r.win_amount == 500 and r.other_winners == 0
    r = page._parse_reward("garbage", 0.1)
    assert r.ok is False and r.win_amount == 0 and r.other_winners == 0

    print("validate_reward_against_db: all checks passed")


if __name__ == "__main__":
    demo()
