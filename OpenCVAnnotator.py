# dagster/OpenCVAnnotator.py
import logging
from datetime import datetime
from pathlib import Path

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logger = logging.getLogger(__name__)

FRAMES_PER_STEP = 22
FRAMES_CROSSFADE = 3
FRAMES_OPENING = 30
FRAMES_ENDING = 30
OUTPUT_FPS = 10


class OpenCVAnnotator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reset()
        return cls._instance

    def _reset(self, test_name: str = ""):
        self.frames: list = []
        self.test_name = test_name
        self.total_steps = 0
        self.fail_count = 0

    @classmethod
    def reset(cls, test_name: str = ""):
        inst = cls()
        inst._reset(test_name)

    def add_step(self, name: str, action: str, screenshot_path: str | None, status: str, timestamp: str):
        if not HAS_CV2 or not screenshot_path:
            return
        try:
            img = cv2.imread(screenshot_path)
            if img is None:
                return
            annotated = self._annotate_frame(img, name, action, status, timestamp)
            self.frames.append(annotated)
            self.total_steps += 1
            if status == "FAIL":
                self.fail_count += 1
        except Exception:
            logger.warning("Failed to annotate step '%s'", name, exc_info=True)

    def _annotate_frame(self, img, name, action, status, timestamp):
        h, w = img.shape[:2]
        status_color = (0, 255, 0) if status == "PASS" else (0, 0, 255)

        cv2.rectangle(img, (0, 0), (6, h), status_color, -1)

        overlay = img.copy()
        cv2.rectangle(overlay, (6, 0), (w, 65), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)

        cv2.putText(img, name, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(img, action, (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        badge_text = f" {status} "
        (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        bx = w - tw - 22
        by = 8
        cv2.rectangle(img, (bx, by), (bx + tw + 8, by + th + 8), status_color, -1)
        cv2.putText(img, badge_text, (bx + 4, by + th + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        cv2.putText(img, timestamp, (16, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        return img

    def finalize(self, overall_status: str, output_path: Path) -> Path | None:
        if not HAS_CV2 or not self.frames:
            return None
        try:
            h, w = self.frames[0].shape[:2]
            writer = None
            for codec in ['avc1', 'mp4v', 'X264']:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                candidate = cv2.VideoWriter(str(output_path), fourcc, OUTPUT_FPS, (w, h))
                if candidate.isOpened():
                    writer = candidate
                    break
                candidate.release()
            if writer is None:
                logger.warning("No working codec found for %s", output_path)
                return None

            opening = self._opening_frame(h, w)
            for _ in range(FRAMES_OPENING):
                writer.write(opening)

            for i in range(len(self.frames)):
                curr = self.frames[i]
                for _ in range(FRAMES_PER_STEP):
                    writer.write(curr)
                if i < len(self.frames) - 1:
                    nxt = self.frames[i + 1]
                    for j in range(FRAMES_CROSSFADE):
                        alpha = (j + 1) / (FRAMES_CROSSFADE + 1)
                        blended = cv2.addWeighted(curr, 1 - alpha, nxt, alpha, 0)
                        writer.write(blended)

            ending = self._ending_frame(h, w, overall_status)
            for _ in range(FRAMES_ENDING):
                writer.write(ending)

            writer.release()

            if output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            return None
        except Exception:
            logger.warning("Failed to finalize video", exc_info=True)
            return None

    def _opening_frame(self, h, w):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        text = self.test_name or "Test"
        font_scale = 1.0 if len(text) < 30 else 0.7
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
        tx = (w - tw) // 2
        ty = h // 2 - 20
        cv2.putText(frame, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (200, 200, 200), 2)
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cv2.putText(frame, date_str, (tx, ty + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        return frame

    def _ending_frame(self, h, w, status):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        is_pass = status == "PASS"
        status_color = (0, 255, 0) if is_pass else (0, 0, 255)

        cv2.putText(frame, status, ((w - cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0][0]) // 2, h // 2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, status_color, 3)

        summary = f"{self.total_steps} step{'s' if self.total_steps != 1 else ''} completed"
        if self.fail_count > 0:
            summary = f"{self.fail_count}/{self.total_steps} step{'s' if self.total_steps != 1 else ''} FAILED"
        cv2.putText(frame, summary, ((w - cv2.getTextSize(summary, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]) // 2, h // 2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cv2.putText(frame, date_str, ((w - cv2.getTextSize(date_str, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0][0]) // 2, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
        return frame
