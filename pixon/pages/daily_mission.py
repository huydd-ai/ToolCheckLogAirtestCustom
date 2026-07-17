# pages/daily_mission.py
from pixon.pages.base_page import BasePage
from pixon.pages.base_page import get_template
from pixon.pages.home_page import HomePage
from airtest.core.api import sleep
from pixon.common import wrappers as wrapper
import time
import cv2
import numpy as np

import functools

# Calibration constants for mission progress detection — tuned for 720×1280 captures.
# Re-calibrate if UI layout or device resolution changes.
_MISSION_BAR_X_START_FRAC = 0.386   # bar left edge as fraction of bounding-box width from right
_MISSION_BAR_X_END_FRAC   = 0.124   # bar right edge as fraction of bounding-box width from right
_MISSION_BAR_Y_FRAC       = 0.020   # bar vertical center as fraction of bounding-box height
_FILL_HSV_LOWER = (35, 50, 50)      # green fill detection lower bound
_FILL_HSV_UPPER = (85, 255, 255)    # green fill detection upper bound
PINS_PER_LEVEL  = 20                # assumed nail count per puzzle level for COLLECT_PIN missions


@functools.lru_cache(maxsize=None)
def _load_missions_db_from_path(db_path: str) -> list:
    import json
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f).get("daily_missions_db", [])


class DailyMissionPage(BasePage):
    btn_daily_mission = get_template(
        "home_page/btn_daily_mission.png", (-0.397, -0.542)
    )
    tap_to_continue = get_template("tap_to_continue.png", (-0.004, 0.55), threshold=0.85)
    btn_close = get_template("system_function/btn_close.png", (0.365, -0.858))
    btn_tutorial = get_template("system_function/btn_tutorial.png", (-0.415, -0.799))
    btn_daily_mission_notify = get_template(
        "home_page/btn_daily_mission_notify.png", (-0.396, -0.543)
    )
    mission_list_panel = get_template(
        "home_page/mission_list_panel.png", (-0.394, -0.544)
    )
    btn_play_daily = get_template("daily_mission/btn_play_daily.png", (0.261, -0.233))
    btn_collect = get_template("daily_mission/btn_collect.png", (0.261, 0.113))
    exp_milestone_boxes = [
        get_template("daily_mission/box_30.png", (-0.124, -0.464)),
        get_template("daily_mission/box_70.png", (0.122, -0.461)),
        get_template("daily_mission/box_100.png", (0.31, -0.463)),
    ]
    icon_reward_claim = get_template(
        "daily_mission/icon_reward_claimed.png", (0.268, 0.454)
    )
    icon_ads_watch = get_template("daily_mission/btn_claim_by_ads.png", (-0.019, 0.656))

    def click_tap_to_continued(self) -> None:
        if wrapper.partial_search(self.tap_to_continue):
            self.tap(self.tap_to_continue)

    def check_daily_mission_appear(self) -> bool:
        HomePage().go_home(force=True)
        self.handle_popup(self.btn_close, timeout=0.5)
        return bool(self.wait_for_element(self.btn_daily_mission, timeout=0.5))

    def is_notify_visible(self, timeout: float = 0.5) -> bool:
        return bool(
            self.wait_for_element(self.btn_daily_mission_notify, timeout=timeout)
        )

    def assert_unlocked(self, timeout: float = 10, notify_timeout: float = 5) -> None:
        if not (
            self.wait_for_element(self.btn_daily_mission, timeout=timeout)
            or self.is_notify_visible(timeout=notify_timeout)
        ):
            raise AssertionError(
                "Daily Mission not unlocked after setup | Actual: icon/notify not visible"
            )

    def open_daily_mission_popup(self, timeout: float = 10) -> bool:
        # Best-effort: returns False on failure (does NOT raise) so callers can
        # decide. log_info is used instead of log_warning because log_warning
        # raises StepError outside an except block.
        if self.wait_for_element(self.btn_daily_mission, timeout=2.5):
            self.tap(self.btn_daily_mission)
        elif self.wait_for_element(self.btn_daily_mission_notify, timeout=1.0):
            self.tap(self.btn_daily_mission_notify)
        else:
            wrapper.log_info("Daily Mission icon not found on home screen")
            return False

        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.wait_for_element(self.tap_to_continue, timeout=0.5):
                self.tap(self.tap_to_continue)
            if self.wait_for_element(self.btn_close, timeout=0.5):
                return True

        wrapper.log_info("open_daily_mission_popup: btn_close not found after tapping icon")
        return False

    def wait_notify_state(
        self, visible: bool, timeout: float = 2.5, interval: float = 0.5
    ) -> bool:
        """Wait until notify icon reaches expected visible state."""
        end_at = time.time() + timeout
        while time.time() < end_at:
            is_visible = self.is_notify_visible(timeout=0.5)
            if is_visible == visible:
                return True
            sleep(interval)
        return False

    def wait_mission_list_loaded(self, timeout: float = 5) -> bool:
        """Wait until mission list is loaded (after join), verified by btn_play_daily or btn_collect."""
        end_at = time.time() + timeout
        while time.time() < end_at:
            if self.get_mission_count() > 0:
                return True
            if self.get_collect_mission_count() > 0:
                return True
            sleep(0.5)
        wrapper.log_info("wait_mission_list_loaded: mission list not loaded within timeout")
        return False

    def verify_daily_mission_icon_on_home(self, timeout: float = 2.5) -> bool:
        home = HomePage()
        home.go_home(force=True)

        end_at = time.time() + timeout
        while time.time() < end_at:
            has_icon = bool(self.wait_for_element(self.btn_daily_mission, timeout=0.5))
            has_notify_icon = bool(
                self.wait_for_element(self.btn_daily_mission_notify, timeout=0.5)
            )
            has_panel = bool(
                self.wait_for_element(self.mission_list_panel, timeout=0.5)
            )

            if has_icon or has_notify_icon or has_panel:
                return True

            # Try one lightweight normalization pass if UI is still transitioning.
            if self.wait_for_element(self.btn_close, timeout=0.5):
                self.tap(self.btn_close)

        wrapper.log_info(
            "verify_daily_mission_icon_on_home: no Daily Mission icon variant found "
            "(icon/notify/panel)"
        )
        return False

    def complete_tutorial_from_popup(self, force_trigger: bool = False, close_after: bool = True) -> None:
        if force_trigger and not self.wait_for_element(self.tap_to_continue, timeout=1):
            if self.wait_for_element(self.btn_tutorial, timeout=1):
                self.tap(self.btn_tutorial)
                sleep(0.5)

        for _ in range(2):
            if self.wait_for_element(self.tap_to_continue, timeout=1):
                self.tap(self.tap_to_continue)
            else:
                break

        if not self.wait_mission_list_loaded(timeout=5):
            wrapper.log_info(
                "complete_tutorial_from_popup: mission list not confirmed before close"
            )

        if close_after:
            if self.wait_for_element(self.btn_close, timeout=4):
                self.tap(self.btn_close)
                sleep(0.5)
            else:
                wrapper.log_info("complete_tutorial_from_popup: btn_close not found")

    def get_mission_count(self) -> int:
        return len(self._find_all_elements(self.btn_play_daily))

    def get_collect_mission_count(self) -> int:
        return len(self._find_all_elements(self.btn_collect))

    def get_icon_claim_reward(self) -> int:
        return len(self._find_all_elements(self.icon_reward_claim))



    def _get_ocr_rows(self, screen, button_templates: list) -> list:
        """Finds buttons matching the templates and groups nearby OCR text into rows."""
        if screen.ndim == 3 and screen.shape[2] == 4:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        ocr = wrapper._get_ocr()
        if not ocr:
            return []
            
        btns = []
        for tmpl in button_templates:
            found = tmpl.match_all_in(screen) or []
            for b in found:
                pos = b["result"] if isinstance(b, dict) else b
                btns.append({"pos": pos, "tmpl": tmpl, "texts": [], "y": pos[1]})
                
        candidates = sorted(btns, key=lambda b: b["pos"][1])
        if not candidates:
            return []
            
        results = ocr.ocr(screen, cls=True)
        if results and results[0]:
            for line in results[0]:
                box = line[0]
                text = line[1][0]
                center_y = sum(p[1] for p in box) / 4.0
                nearest = min(candidates, key=lambda c: abs(c["y"] - center_y))
                if abs(nearest["y"] - center_y) < 60:
                    nearest["texts"].append(text)
                
        for c in candidates:
            c["text_joined"] = " ".join(c["texts"])
            c["text_clean"] = c["text_joined"].lower().replace(" ", "")
            
        return candidates

    @staticmethod
    def _fuzzy_match_score(target_exact: str, candidate_clean: str) -> float:
        """Returns 1.0 for exact substring match, difflib ratio for fuzzy, 0.0 otherwise."""
        if target_exact in candidate_clean:
            return 1.0
            
        import re
        import difflib
        # Remove digits and slashes so 'Complete 2 Lucky Spins 1/2' becomes 'Complete  Lucky Spins '
        target_base = re.sub(r'[\d/]+', '', target_exact)
        cand_base = re.sub(r'[\d/]+', '', candidate_clean)
        
        if target_base and target_base in cand_base:
            return difflib.SequenceMatcher(None, target_exact, candidate_clean).ratio()
            
        return 0.0

    def _find_mission_row(self, img, mission_name: str, button_templates: list) -> dict:
        candidates = self._get_ocr_rows(img, button_templates)
        if not candidates:
            wrapper.log_info(f"_find_mission_row: No buttons found for '{mission_name}'")
            return None

        target_exact = mission_name.lower().replace(" ", "")
        best_match = None
        best_ratio = 0.0
        
        for c in candidates:
            ratio = self._fuzzy_match_score(target_exact, c["text_clean"])
            if ratio == 1.0:
                return c
            elif ratio > best_ratio:
                best_ratio = ratio
                best_match = c
                
        if best_match:
            wrapper.log_info(f"_find_mission_row: Fuzzy matched '{mission_name}' to '{best_match['text_joined']}' (ratio: {best_ratio:.2f})")
            return best_match

        available = [c["text_joined"] for c in candidates]
        wrapper.log_info(f"_find_mission_row: '{mission_name}' not found. Available: {available}")
        return None

    def take_mission_by_name(self, mission_name: str) -> str:
        screen = wrapper.get_screen()
        row = self._find_mission_row(screen, mission_name, [self.btn_play_daily])
        if row is None:
            return ""
        self.tap(row["pos"])
        return " ".join(row["texts"])

    def get_mission_progress(self, mission_name: str) -> int:
        """Return the named mission's progress-bar fill % (0..100).

        Assumes the Daily Mission popup is ALREADY OPEN. Returns 100 if the
        row shows COLLECT (mission complete), -1 if the mission is not found
        or OCR is unavailable. Best-effort: logs via log_info, never raises.
        """
        screen = wrapper.get_screen()
        row = self._find_mission_row(
            screen, mission_name, [self.btn_play_daily, self.btn_collect]
        )
        if row is None:
            return -1
        if row["tmpl"] is self.btn_collect:
            wrapper.log_info(f"get_mission_progress: '{mission_name}' shows COLLECT -> 100%")
            return 100
        x_start, x_end, y = self._mission_bar_roi(screen, row)
        return self._parse_mission_fill(screen, x_start, x_end, y)

    def _load_mission_db(self, db_path: str = None) -> list:
        import os
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                "Test", "DailyMission", "missions_db.json"
            )
        return _load_missions_db_from_path(os.path.abspath(db_path))

    def verify_mission_and_claim(self, mission_id: str, db_path: str = None) -> bool:
        """
        Generic method to verify a mission is complete, tap Collect,
        wait for Claimed icon, and assert global EXP increased.
        """
        db = self._load_mission_db(db_path)
        mission_data = next((m for m in db if m["id"] == mission_id), None)
        if not mission_data:
            wrapper.log_info(f"verify_mission_and_claim: '{mission_id}' not found in DB")
            return False
            
        mission_name = mission_data["ocr_text"]
        
        # 1. Record Initial EXP
        initial_exp = self.get_exp_progress()
        
        # 2. Check individual progress bar is 100% and button is COLLECT
        screen = wrapper.get_screen()
        row = self._find_mission_row(screen, mission_name, [self.btn_play_daily, self.btn_collect, self.icon_reward_claim])
        
        if row is None:
            raise AssertionError(f"Mission '{mission_name}' not found on screen.")
            
        if row["tmpl"] is self.icon_reward_claim:
            wrapper.log_info(f"Mission '{mission_name}' already claimed.")
            return True
            
        if row["tmpl"] is self.btn_play_daily:
            progress = self.get_mission_progress(mission_name)
            raise AssertionError(f"Mission '{mission_name}' is not complete. Current progress: {progress}%")
            
        if row["tmpl"] is self.btn_collect:
            # Double-check the bar is visually 100% (since collect is present)
            progress = self.get_mission_progress(mission_name)
            if progress < 100:
                wrapper.log_info(f"Note: btn_collect present but get_mission_progress returned {progress}%. Assuming 100% due to btn_collect.")

            # 3. Tap COLLECT
            self.tap(row["pos"])
            sleep(2)
            self._confirm_claim_popup()
                
            # 4. Wait for it to become CLAIMED icon
            end_at = time.time() + 5
            claimed = False
            while time.time() < end_at:
                screen = wrapper.get_screen()
                updated_row = self._find_mission_row(screen, mission_name, [self.icon_reward_claim])
                if updated_row and updated_row["tmpl"] is self.icon_reward_claim:
                    claimed = True
                    break
                sleep(0.5)
                
            if not claimed:
                raise AssertionError(f"Mission '{mission_name}' button did not change to claimed icon after tap.")
                
            # 5. Wait for EXP bar animation to finish and check global EXP increased
            # The animation can take a variable amount of time, so we poll for up to 10 seconds.
            end_at = time.time() + 10
            new_exp = initial_exp
            while time.time() < end_at:
                new_exp = self.get_exp_progress()
                if new_exp != initial_exp:
                    break
                sleep(1)
                
            # If new_exp is exactly the same after 10s, the bar didn't move.
            # If new_exp < initial_exp, it likely wrapped around 100% to the next level.
            if new_exp == initial_exp and initial_exp != 100:
                raise AssertionError(f"Global EXP did not increase after 10s! Before: {initial_exp}%, After: {new_exp}%")
                
            wrapper.log_info(f"Successfully verified and claimed '{mission_name}'. EXP increased {initial_exp}% -> {new_exp}%")
            return True
            
        return False

    def is_mission_completable(self, mission_id: str, db_path: str = None) -> bool:
        """Return True iff the mission row currently shows COLLECT or the
        already-claimed icon (i.e. ready to claim, or already claimed).

        Read-only counterpart to verify_mission_and_claim — useful as a retry
        predicate when a play loop may need more than one attempt to finish.
        Returns False (does not raise) when the id is unknown or the row is
        not visible. Caller is expected to already be on the daily-mission
        popup screen.
        """
        db = self._load_mission_db(db_path)
        mission_data = next((m for m in db if m["id"] == mission_id), None)
        if not mission_data:
            wrapper.log_info(
                f"is_mission_completable: '{mission_id}' not found in DB"
            )
            return False
        mission_name = mission_data["ocr_text"]
        screen = wrapper.get_screen()
        row = self._find_mission_row(
            screen,
            mission_name,
            [self.btn_play_daily, self.btn_collect, self.icon_reward_claim],
        )
        if row is None:
            return False
        return row["tmpl"] is self.btn_collect or row["tmpl"] is self.icon_reward_claim

    def _get_mission_ids_by_button(self, btn_template, db_path: str = None) -> list:
        db = self._load_mission_db(db_path)
        screen = wrapper.get_screen()
        
        rows = self._get_ocr_rows(screen, [btn_template])
        if not rows:
            return []
            
        ids = set()
        for row in rows:
            best_id = None
            best_ratio = 0.0
            
            for m in db:
                target_exact = m["ocr_text"].lower().replace(" ", "")
                ratio = self._fuzzy_match_score(target_exact, row["text_clean"])
                
                if ratio == 1.0:
                    best_id = m["id"]
                    break
                elif ratio > best_ratio:
                    best_ratio = ratio
                    best_id = m["id"]
                    
            if best_id:
                ids.add(best_id)
                
        return list(ids)

    def get_claimable_mission_ids(self, db_path: str = None) -> list:
        """Dynamically detect which missions on the screen are claimable."""
        return self._get_mission_ids_by_button(self.btn_collect, db_path)

    def get_active_mission_ids(self, db_path: str = None) -> list:
        """Dynamically detect which missions on the screen are active (PLAY button)."""
        return self._get_mission_ids_by_button(self.btn_play_daily, db_path)

    def find_active_mission_by_type(
        self,
        task_type: str,
        target_item: str = None,
        db_path: str = None,
    ) -> dict:
        """Return the first active mission matching task_type (and optional target_item), or None.

        Pure query — does not advance the clock or restart the app. Callers handle reroll.
        """
        active_ids = self.get_active_mission_ids(db_path)
        db = self._load_mission_db(db_path)
        
        matches = []
        for m in db:
            if m["id"] not in active_ids:
                continue
            if m["task_type"] != task_type:
                continue
            if target_item is not None and m.get("target_item") != target_item:
                continue
            matches.append(m)
            
        if not matches:
            return None
            
        # Return the easiest mission of this specific type
        return min(matches, key=lambda m: float(m.get("target_amount", 100)))


    def get_easiest_mission_id(self, mission_ids: list, db_path: str = None) -> str:
        """Given a list of mission IDs, return the one with the lowest effort score."""
        if not mission_ids:
            return None
            
        db = self._load_mission_db(db_path)
        available_missions = [m for m in db if m["id"] in mission_ids]
        
        if not available_missions:
            return mission_ids[0]
            
        def effort_score(m):
            task_type = m.get("task_type", "")
            amount = float(m.get("target_amount", 100))
            if "PIN" in task_type or "SCREW" in task_type:
                return amount / 50.0
            if "LEVEL" in task_type:
                return amount / 1.0
            if "BOOSTER" in task_type or "DRILL" in task_type or "HAMMER" in task_type or "MAGNET" in task_type:
                return amount / 2.0
            return amount
            
        return min(available_missions, key=effort_score)["id"]

    def find_or_reroll_mission(
        self,
        task_type: str,
        target_items=None,
        home_page=None,
        max_rerolls: int = 15,
        db_path: str = None,
    ):
        """Return (mission_dict, matched_item) or (None, None) after exhausting rerolls.

        Searches for an active mission with the given task_type. If `target_items`
        is a list, returns the first mission whose target_item matches any entry.
        If None, target_item is not filtered (use for single-mission task types).

        On miss, resets the daily missions via the cheat console and retries up to `max_rerolls` times.
        Caller must pass `home_page` to allow navigation; raises ValueError if not provided.
        """
        from pixon.common.test_flow import run_step

        if home_page is None:
            raise ValueError("find_or_reroll_mission requires home_page for navigation")

        def _search():
            if target_items is None:
                m = self.find_active_mission_by_type(task_type, db_path=db_path)
                return (m, None) if m else (None, None)
            for item in target_items:
                m = self.find_active_mission_by_type(task_type, target_item=item, db_path=db_path)
                if m:
                    wrapper.log_info(f"Found active mission for item: {item}")
                    return m, item
            return None, None

        mission, found_item = _search()
        for reroll in range(1, max_rerolls + 1):
            if mission:
                return mission, found_item
            wrapper.log_info(
                f"Reroll {reroll}/{max_rerolls}: no active {task_type} for {target_items}, resetting via cheat"
            )
            
            run_step(f"Reroll {reroll}: close daily mission", self.tap, self.btn_close)
            
            from pixon.pages.cheat_page import CheatPage
            cheat = CheatPage()
            run_step(f"Reroll {reroll}: open cheat", cheat.open_cheat)
            run_step(f"Reroll {reroll}: reset daily mission", cheat.reset_daily_mission)
            
            run_step(f"Reroll {reroll}: reopen daily mission popup", self.open_daily_mission_popup)
            if not self.wait_mission_list_loaded(timeout=5):
                wrapper.log_info(f"Reroll {reroll}: mission list not confirmed loaded")
            mission, found_item = _search()
        return mission, found_item

    def use_booster_for_mission(self, game_page, booster_name: str, count: int) -> None:
        """Warm-grant exactly `count` boosters of `booster_name`, then use them.

        Grant is exact (no buffer): the warm `booster` payload sets inventory to an
        absolute value and the cold start omits booster, so {booster_name: count}
        leaves exactly `count`. Caller (execute_mission_logic) resolves the type and
        the count (remaining_amount). Best-effort: a failed warm send is logged via
        log_info (log_warning raises), never raised.
        """
        from pixon.common.adb_utils import set_param
        import time
        if not set_param("booster", {booster_name: count}):
            wrapper.log_info(
                f"use_booster_for_mission: warm grant returned False for "
                f"{{{booster_name}: {count}}}"
            )
        time.sleep(0.5)
        game_page.use_booster(booster_name, count)

    def execute_mission_logic(self, mission_id: str, game_page, home_page, db_path: str = None, partial: bool = False):
        """Universal execution engine to play the game and complete a specific mission."""
        import math
        from pixon.common.adb_utils import set_param
        from pixon.common.test_flow import go_home_clean, close_all_popups
        from pixon.common.autoplay_watchdog import autoplay_with_watchdog
        
        db = self._load_mission_db(db_path)
        mission_data = next((m for m in db if m["id"] == mission_id), None)
        if not mission_data:
            wrapper.log_error(f"execute_mission_logic: '{mission_id}' not found in DB")
            return
            
        task_type = mission_data.get("task_type")
        target_amount = mission_data.get("target_amount", 1)
        target_item = mission_data.get("target_item")
        
        def play_and_win_target(target_lvl):
            autoplay_with_watchdog(
                game_page, 
                target_lvl, 
                booster={"drill": 30, "hammer": 30, "magnet": 30}
            )

        # 1. Ensure Daily Mission popup is open
        if not wrapper.partial_search(self.btn_close):
            close_all_popups(home_page)
            home_page.go_home(force=True)
            if not self.open_daily_mission_popup():
                wrapper.log_info("Failed to open daily mission popup to check progress.")
                return

        screen = wrapper.get_screen()
        row = self._find_mission_row(
            screen, mission_data["ocr_text"], [self.btn_play_daily, self.btn_collect]
        )

        if row:
            actual_ocr_text = " ".join(row["texts"])
            import re
            matches = re.findall(r'\d+', actual_ocr_text)
            if matches:
                target_amount = int(matches[0])
                wrapper.log_info(f"Parsed target_amount={target_amount} from screen OCR: '{actual_ocr_text}'")

        wrapper.log_info(f"Executing mission logic for {mission_id} ({task_type}, target_amount={target_amount})")
        
        if row is None:
            wrapper.log_info(f"Could not read progress for mission '{mission_data['ocr_text']}', assuming 0%.")
            progress = 0
        elif row["tmpl"] is self.btn_collect:
            wrapper.log_info(f"Mission '{mission_data['ocr_text']}' shows COLLECT -> 100%")
            progress = 100
        else:
            x_start, x_end, y = self._mission_bar_roi(screen, row)
            progress = self._parse_mission_fill(screen, x_start, x_end, y)
        
        if progress >= 100:
            wrapper.log_info(f"Mission '{mission_data['ocr_text']}' is 100% complete.")
            self.tap(self.btn_close)
            return
            
        remaining_amount = max(1, math.ceil(target_amount * (100 - progress) / 100.0))
        if partial:
            remaining_amount = 1
            wrapper.log_info("Mission partial=True, forcing remaining amount to 1")
        else:
            wrapper.log_info(f"Mission at {progress}%, calculating remaining amount: {remaining_amount}")
        
        # Tap the mission's PLAY button to navigate directly
        if row is not None and row["tmpl"] is self.btn_play_daily:
            self.tap(row["pos"])
        else:
            # Fallback if play button not found
            self.take_mission_by_name(mission_data["ocr_text"])
            
        time.sleep(2)
        
        # Execute logic based on remaining_amount
        if task_type == "COMPLETE_LEVEL":
            target_level = game_page.get_current_level() + remaining_amount
            play_and_win_target(target_level)
            
        elif task_type in ["USE_BOOSTER", "USE_ITEM"]:
            booster_name = target_item if target_item != "any_booster" else "drill"
            self.use_booster_for_mission(game_page, booster_name, remaining_amount)
            # Ensure we progress slightly or at least exit cleanly
            target_level = game_page.get_current_level() + 1
            play_and_win_target(target_level)
            
        elif task_type == "USE_MONEY":
            set_param("coin", remaining_amount + 1000)
            time.sleep(1)
            target_level = game_page.get_current_level() + 2
            play_and_win_target(target_level)
            game_page.spend_coins(remaining_amount)
            
        elif task_type == "COLLECT_PIN":
            time.sleep(1)
            set_param("level", game_page.get_current_level())
            
            # Assuming ~20 pins per level
            lvls_to_play = max(1, math.ceil(remaining_amount / float(PINS_PER_LEVEL)))
            wrapper.log_info(f"COLLECT_PIN: Need {remaining_amount} pins, playing {lvls_to_play} levels.")
                
            target_level = game_page.get_current_level() + lvls_to_play
            play_and_win_target(target_level)
            
        elif task_type == "COMPLETE_SPIN":
            from pixon.pages.lucky_spin import LuckySpinPage
            lucky = LuckySpinPage()
            time.sleep(2)
            for i in range(remaining_amount):
                if i > 0 and wrapper.partial_search(self.icon_ads_watch):
                    wrapper.log_info("Watching ad for another spin turn")
                    self.tap(self.icon_ads_watch)
                else:
                    lucky.spin()
                time.sleep(5)
            close_all_popups(home_page)
            
        else:
            from pixon.common.logging_utils import StepError
            raise StepError(
                f"execute_mission_logic: unhandled task_type={task_type!r} "
                f"for mission_id={mission_id!r}. "
                "Either add a branch or set is_active:false in missions_db.json."
            )
            
        go_home_clean(home_page)

    def watch_ads(self) -> None:
        self.tap(self.icon_ads_watch)

    def get_exp_progress(self) -> int:
        opened_here = False
        if not wrapper.partial_search(self.btn_close):
            if wrapper.partial_search(self.btn_daily_mission):
                self.tap(self.btn_daily_mission)
            self.wait_for_element(self.btn_close, timeout=2.5)
            opened_here = True

        @wrapper.retry(times=3, delay=1, exceptions=(Exception,), failure_values=(None,))
        def _attempt():
            screen = wrapper.get_screen()
            box30 = self.exp_milestone_boxes[0].match_in(screen)
            box100 = self.exp_milestone_boxes[2].match_in(screen)
            return self._parse_exp_fill(screen, box30, box100)

        try:
            result = _attempt()
        finally:
            if opened_here:
                if self.wait_for_element(self.btn_close, timeout=1):
                    self.tap(self.btn_close)
        return result if result is not None else 0

    @staticmethod
    def _parse_exp_fill(screen, box30, box100) -> int:
        """Compute EXP-bar fill % from a snapshot and the 30%/100% milestone
        box coordinates. Pure (no device, no match_in) so it is unit-testable.

        Owns the BGRA->BGR guard: G.DEVICE.snapshot() is 4-channel BGRA on the
        target devices, and the per-pixel `b, g, r = pixel` unpack below requires
        3 channels. Without this guard the method raises ValueError on device.
        """
        if screen.ndim == 3 and screen.shape[2] == 4:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)

        if not box30 or not box100:
            return 0

        x30, y30 = box30
        x100, _ = box100

        if x100 <= x30:
            return 0

        x_start = int(x30 - 30 * (x100 - x30) / 70)
        total_width = float(x100 - x_start)

        row = screen[int(y30), int(x_start):int(x100)]
        filled_dx = 0
        dx30 = x30 - x_start
        dx70 = dx30 + 40 * (x100 - x30) / 70
        dx100 = x100 - x_start

        for i, pixel in enumerate(row):
            if abs(i - dx30) < 35 or abs(i - dx70) < 35 or abs(i - dx100) < 35:
                continue

            b, g, r = pixel
            is_green = int(g) > int(r) + 20 and int(g) > int(b) + 20 and int(g) > 80

            if is_green:
                filled_dx = i

        if filled_dx == 0:
            return 0

        return min(100, int((filled_dx / total_width) * 100))

    @staticmethod
    def _parse_mission_fill(screen, x_start, x_end, y) -> int:
        """Per-mission progress-bar fill % (0..100) from a snapshot.

        Self-calibrating: isolates green pixels to measure the width of the fill,
        ignoring white text overlays like '0/5'.
        BGRA->BGR guarded (snapshots are 4-channel on target devices). Pure
        (no device, no match_in) -> unit-testable offline.

        Assumes a partially-filled bar (a dark region remains); the all-bright
        100% case is handled by get_mission_progress's COLLECT short-circuit.
        """
        if screen.ndim == 3 and screen.shape[2] == 4:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)

        x_start, x_end = int(x_start), int(x_end)
        if x_end <= x_start:
            return 0

        h = screen.shape[0]
        y = max(0, min(int(y), h - 1))
        
        # Extract row as a 2D image (1 pixel high) for cvtColor
        row_img = screen[y:y+1, x_start:x_end]
        if row_img.shape[1] < 2:
            return 0

        # Convert to HSV to isolate green color perfectly
        hsv_row = cv2.cvtColor(row_img, cv2.COLOR_BGR2HSV)
        
        # Define HSV bounds for Green
        lower_green = np.array(_FILL_HSV_LOWER)
        upper_green = np.array(_FILL_HSV_UPPER)
        
        green_mask = cv2.inRange(hsv_row, lower_green, upper_green)
        
        # Find indices of all green pixels
        filled = np.where(green_mask[0] > 0)[0]
        
        if filled.size == 0:
            return 0

        last = int(filled.max())
        width = float(row_img.shape[1] - 1)
        return min(100, int(round((last / width) * 100)))

    @staticmethod
    def _mission_bar_roi(screen, row):
        """Compute the (x_start, x_end, y) progress-bar scan line for a row
        dict from _find_mission_row. BUTTON-ANCHORED: the bar sits at fixed
        offsets left of and below the row's PLAY/COLLECT button.

        An earlier version anchored x_start on the mission-name OCR text
        (text_xmin), but reward-number text ("20"/"5") on the same row binds
        into the row and drags text_xmin into the bright reward-icon zone,
        so the scan crossed the icons and read an EMPTY bar as 100% full.
        Anchoring purely off the button avoids that contamination.

        Fractions calibrated on a 720x1280 capture (button x=548 -> bar
        x[270..459], y-center ~498); re-tune via the capture gate if the UI
        layout changes."""
        h, w = screen.shape[:2]
        bx, by = row["pos"]
        x_start = int(bx - _MISSION_BAR_X_START_FRAC * w)
        x_end = int(bx - _MISSION_BAR_X_END_FRAC * w)
        y = int(by + _MISSION_BAR_Y_FRAC * h)
        return x_start, x_end, y

    def _confirm_claim_popup(self, post_tap_sleep: float = 1.0) -> None:
        """Tap the 'tap to claim' confirmation popup if visible."""
        from pixon.pages.home_page import HomePage
        if wrapper.partial_search(HomePage.tap_to_claim):
            self.tap(HomePage.tap_to_claim)
            sleep(post_tap_sleep)

    def claim_exp_reward(self, milestone: int) -> bool:
        index = {30: 0, 70: 1, 100: 2}.get(milestone, -1)
        if index == -1:
            wrapper.log_info(f"claim_exp_reward: unknown milestone {milestone}")
            return False
        if self.wait_for_element(self.exp_milestone_boxes[index], timeout=0.5):
            self.tap(self.exp_milestone_boxes[index])
            sleep(2)
            self._confirm_claim_popup()
            return True
        return False

    def _find_all_elements(self, template) -> list:
        screen = wrapper.get_screen()
        pos = template.match_all_in(screen)
        return pos if pos else []

    def claim_all_other_completed_missions(self) -> None:
        while True:
            collect_btns = self._find_all_elements(self.btn_collect)
            if not collect_btns:
                break
            btn_pos = collect_btns[0]["result"] if isinstance(collect_btns[0], dict) else collect_btns[0]
            self.tap(btn_pos)
            sleep(2)
            self._confirm_claim_popup()

    def claim_all_exp_boxes(self) -> None:
        for m in [30, 70, 100]:
            if self.claim_exp_reward(m):
                sleep(2)
                self._confirm_claim_popup()
