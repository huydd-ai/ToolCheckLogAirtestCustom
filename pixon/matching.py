import os
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from airtest.core.api import G, log, sleep, Template
from airtest.aircv import crop_image

_last_match_pos: Optional[Tuple[float, float]] = None

def _extract_pos(result) -> Optional[Tuple[float, float]]:
    """Normalize a raw Airtest match result to an (x, y) tuple, or None."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], (int, float)):
        return result
    if isinstance(result, list):
        if len(result) == 0:
            return None
        if isinstance(result[0], dict):
            pos = result[0].get("result")
            if pos is not None and len(pos) >= 2:
                return (pos[0], pos[1])
        return None
    if isinstance(result, dict):
        pos = result.get("result")
        if pos is not None and len(pos) >= 2:
            return (pos[0], pos[1])
    return None

class SmartTemplate:
    def __init__(self, path, record_pos=None, thresholds=None, **kwargs):
        self.template = Template(path, record_pos=record_pos, **kwargs)
        self.template.scale_step = 0.02  # match plain-template path via default_img_setup
        self.thresholds = thresholds or [0.6, 0.5]

def default_img_setup(img):
    # ponytail: scale_step=0.02 serves as our "already initialized" flag, no need for custom attributes or tracking sets
    if isinstance(img, Template) and getattr(img, "scale_step", None) != 0.02:
        img.rgb = False
        img.threshold = 0.7
        img.target_pos = 5
        img.scale_max = 800
        img.scale_step = 0.02
    return img

def _img_name(img) -> str:
    import os
    if isinstance(img, SmartTemplate):
        return os.path.splitext(os.path.basename(img.template.filepath))[0]
    return os.path.splitext(os.path.basename(img.filepath))[0]

def _silent_match(img: Template, screen):
    logger = G.LOGGER
    _logfd = None
    if logger:
        _logfd, logger.logfd = logger.logfd, None
    try:
        return img.match_in(screen)
    finally:
        if logger:
            logger.logfd = _logfd

def _smart_search(smart_tmpl: SmartTemplate, screen):
    for thresh in smart_tmpl.thresholds:
        smart_tmpl.template.threshold = thresh
        result = _silent_match(smart_tmpl.template, screen)
        if result is not None:
            return result
    return None

def partial_search(img, area=None):
    global _last_match_pos
    
    if not isinstance(img, SmartTemplate):
        img = default_img_setup(img)
        raw_img = getattr(img, "_image", None) or getattr(img, "im_search", None)
        if raw_img is None:
            import cv2 as _cv2
            loaded = _cv2.imread(img.filepath)
            if loaded is None:
                raise RuntimeError(
                    f"Template image could not be read (corrupt or missing): "
                    f"{img.filepath!r}\n"
                    f"  → Capture from a live device and replace the file."
                )
            if loaded.shape[:2] == (1, 1):
                raise RuntimeError(
                    f"Template image is a 1×1 placeholder stub: {img.filepath!r}\n"
                    f"  → Capture the real screenshot from a device and replace this stub."
                )
                
    screen = G.DEVICE.snapshot()
    if area:
        local_screen = crop_image(screen, area)
        if local_screen is None or local_screen.size == 0:
            _last_match_pos = None
            return None
        
        if isinstance(img, SmartTemplate):
            result = _smart_search(img, local_screen)
        else:
            result = _silent_match(img, local_screen)

        if result is not None and len(result) > 0:
            pos = _extract_pos(result)
            _last_match_pos = (pos[0] + area[0], pos[1] + area[1]) if pos is not None else None
        else:
            _last_match_pos = None
        return result
        
    if isinstance(img, SmartTemplate):
        result = _smart_search(img, screen)
    else:
        result = _silent_match(img, screen)
        
    if result is not None and len(result) > 0:
        pos = _extract_pos(result)
        _last_match_pos = pos  # None if no match
    else:
        _last_match_pos = None
    return result

def wait_stable(
    area: Optional[tuple] = None,
    timeout: float = 10.0,
    settle_interval: float = 0.2,
    stable_required: int = 3,
    max_diff: Optional[float] = None,
) -> bool:
    """Wait until screen stops animating. Returns True if stable within timeout.

    3 consecutive under-threshold diffs = stable. Threshold defaults to
    img.max() * 0.02 (auto-scales with bit depth). Area scoping lets callers
    ignore unrelated animations (e.g., a spinning timer while checking popup).
    """
    start = time.time()
    stable_count = 0
    prev = G.DEVICE.snapshot()
    if prev is None:
        return False
    if area is not None:
        prev = crop_image(prev, area)
        if prev is None or prev.size == 0:
            return False

    while time.time() - start < timeout:
        sleep(settle_interval)
        curr = G.DEVICE.snapshot()
        if curr is None:
            continue
        if area is not None:
            curr = crop_image(curr, area)
            if curr is None or curr.size == 0:
                continue
        if prev.shape != curr.shape:
            stable_count = 0
            prev = curr
            continue
        threshold = max_diff if max_diff is not None else (curr.max() * 0.02)
        diff = cv2.absdiff(prev, curr)
        mean_diff = float(np.mean(diff))
        if mean_diff < threshold:
            stable_count += 1
            if stable_count >= stable_required:
                return True
        else:
            stable_count = 0
        prev = curr
    return False


def wait_not_exists(img, timeout=45, interval=0.2, area=None, snapshot=True, stabilize=True):
    if not isinstance(img, SmartTemplate):
        img = default_img_setup(img)
    if stabilize:
        wait_stable(timeout=min(timeout, 10))
    start_time = time.time()
    while partial_search(img, area):
        if time.time() - start_time > timeout:
            log(f"match with {_img_name(img)}: still visible after {timeout}s", snapshot=snapshot)
            return False
        sleep(interval)
    log(f"match with {_img_name(img)}: gone", snapshot=snapshot)
    return True

# ponytail: 0.4s poll — template match costs ~0.1-0.3s itself; 0.1s interval just pegged a core
def wait_exists(img, timeout=45, interval=0.4, area=None, snapshot=True, stabilize=True):
    if not isinstance(img, SmartTemplate):
        img = default_img_setup(img)
    if stabilize:
        wait_stable(timeout=min(timeout, 10))
    start_time = time.time()
    result = partial_search(img, area)
    while not result:
        if time.time() - start_time > timeout:
            log(f"match with {_img_name(img)}: not found after {timeout}s", snapshot=snapshot)
            return False
        sleep(interval)
        result = partial_search(img, area)
    log(f"match with {_img_name(img)}: found", snapshot=snapshot)
    return result

def wait_exists_pos(img, timeout=45, interval=0.4, area=None) -> Optional[Tuple[float, float]]:
    """Like wait_exists but returns the normalized match (x, y) or None.
    Reads _last_match_pos atomically after the match — avoids callers
    reaching into the private global and racing with record_failure resets."""
    result = wait_exists(img, timeout=timeout, interval=interval, area=area, snapshot=False)
    if not result:
        return None
    return _last_match_pos
