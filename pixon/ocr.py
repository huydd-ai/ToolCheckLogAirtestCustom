import re
import logging
import cv2
import numpy as np
from typing import NamedTuple

from airtest.core.api import G
from airtest.aircv import crop_image

_logger = logging.getLogger("pixon")


class OcrLine(NamedTuple):
    text: str
    conf: float

class OcrBox(NamedTuple):
    text: str
    conf: float
    bbox: tuple  # (x, y, w, h)


_ocr = None
_ocr_import_error = None

def _get_ocr():
    global _ocr, _ocr_import_error
    if _ocr is None and _ocr_import_error is None:
        try:
            import os
            os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
            from paddleocr import PaddleOCR

            _ocr = PaddleOCR(
                use_angle_cls=False,
                lang="en",
                use_gpu=False,
                show_log=False,
                # ponytail: 4 threads ≈ same latency on i5-12400F, well under full machine load;
                # bump if OCR latency regresses on a bigger box
                cpu_threads=4,
                enable_mkldnn=True,
                det_db_thresh=0.2,
                det_db_box_thresh=0.5,
                drop_score=0.4,
            )
        except ImportError as e:
            _ocr_import_error = e
            _logger.warning("PaddleOCR not installed.")
        except Exception as e:
            _ocr_import_error = e
            _logger.warning("Failed to initialize PaddleOCR: %s", e)
    return _ocr


# Pre-warm PaddleOCR at import time so the first find_all_text call is fast
_get_ocr()


def find_all_text_with_conf(img_array: np.ndarray, min_conf: float = 0.4) -> list:
    # min_conf default matches PaddleOCR's drop_score=0.4 above (no-op at default);
    # the param exists so callers can demand a stricter threshold.
    ocr_instance = _get_ocr()
    if ocr_instance is None:
        raise RuntimeError("PaddleOCR is not initialized. Check your environment.")
    try:
        if img_array.ndim == 3 and img_array.shape[2] == 4:
            img = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        else:
            img = img_array
        h = img.shape[0]
        if h and h < 200:
            scale = 200.0 / float(h)
            new_w = int(round(img.shape[1] * scale))
            new_h = int(round(h * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        results = ocr_instance.ocr(img, cls=False)
        if not results or results[0] is None:
            return []
        return [OcrLine(line[1][0], float(line[1][1])) for line in results[0] if line[1][1] >= min_conf]
    except Exception as e:
        raw = str(e).strip().splitlines()
        msg = type(e).__name__
        for line in reversed(raw):
            line = line.strip()
            if not line or line.startswith(("File ", "[", "in ")):
                continue
            if line.lower() in ("in user code:",):
                continue
            msg = line
            break
        raise RuntimeError(f"PaddleOCR failed: {msg}") from e


def find_all_text(img_array: np.ndarray) -> list:
    return [line.text for line in find_all_text_with_conf(img_array)]

def find_text_boxes(img_array: np.ndarray, text_target: str, min_conf: float = 0.4) -> list:
    ocr_instance = _get_ocr()
    if ocr_instance is None:
        raise RuntimeError("PaddleOCR is not initialized. Check your environment.")
    try:
        if img_array.ndim == 3 and img_array.shape[2] == 4:
            img = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        else:
            img = img_array.copy()
            
        scale = 1.0
        h = img.shape[0]
        if h and h < 200:
            scale = 200.0 / float(h)
            new_w = int(round(img.shape[1] * scale))
            new_h = int(round(h * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
        results = ocr_instance.ocr(img, cls=False)
        if not results or results[0] is None:
            return []
            
        boxes = []
        for line in results[0]:
            conf = float(line[1][1])
            text = line[1][0]
            if conf >= min_conf and text_target.lower() in text.lower():
                points = np.array(line[0], dtype=np.float32)
                x, y, w, box_h = cv2.boundingRect(points)
                
                x = int(x / scale)
                y = int(y / scale)
                w = int(w / scale)
                box_h = int(box_h / scale)
                
                boxes.append(OcrBox(text, conf, (x, y, w, box_h)))
        return boxes
    except Exception as e:
        raise RuntimeError(f"PaddleOCR failed: {e}") from e

def is_text_present(text_value: str, area=None) -> bool:
    screen = G.DEVICE.snapshot()
    if area:
        screen = crop_image(screen, area)
        if screen is None or screen.size == 0:
            return False
    texts = find_all_text(screen)
    return any(text_value.lower() in t.lower() for t in texts)

def detect_level_badge(screen_bgr: np.ndarray):
    # Normalize to 3-channel BGR — snapshot() returns 4-channel BGRA on real devices
    if screen_bgr.ndim == 3 and screen_bgr.shape[2] == 4:
        screen_bgr = screen_bgr[:, :, :3]
    ranges = [
        (np.array([0, 0, 0]), np.array([180, 80, 80])),
        (np.array([0, 0, 100]), np.array([80, 80, 255])),
        (np.array([80, 0, 0]), np.array([255, 80, 180])),
    ]
    best_bbox = None
    best_area = 0
    for lo, hi in ranges:
        mask = cv2.inRange(screen_bgr, lo, hi)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area > best_area and 20 < w < 200 and 10 < h < 80:
                best_area = area
                best_bbox = (x, y, w, h)
    return best_bbox

def read_level_from_badge(screen_bgr: np.ndarray, bbox):
    x, y, w, h = bbox
    pad = 4
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(screen_bgr.shape[1], x + w + pad)
    y2 = min(screen_bgr.shape[0], y + h + pad)
    crop_bgr = screen_bgr[y1:y2, x1:x2]
    texts = find_all_text(crop_bgr)
    for t in texts:
        if "level" in t.lower():
            m = re.search(r"\d+", t)
            if m:
                return int(m.group())
    for t in texts:
        m = re.search(r"\d+", t)
        if m:
            return int(m.group())
    return None
