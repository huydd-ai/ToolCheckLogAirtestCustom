import os
import time
import json
import logging
import functools
import subprocess
from pathlib import Path
from typing import Union, Optional, Tuple, Any

import numpy as np

from airtest.core.api import (
    G,
    ST,
    Template,
    log,
    start_app,
    stop_app,
    swipe,
    touch,
    wait,
    pinch,
    sleep,
)
from airtest.aircv import crop_image

_logger = logging.getLogger("pixon")

# --- Monkey-patch Airtest to fix cv2.findHomography crash with < 4 points ---
try:
    from airtest.aircv.keypoint_base import KeypointMatching
    from airtest.aircv.error import HomographyError
    
    _orig_find_homography = KeypointMatching._find_homography
    
    def _safe_find_homography(self, sch_pts, src_pts):
        if len(sch_pts) < 4:
            raise HomographyError("Not enough points to find homography")
        return _orig_find_homography(self, sch_pts, src_pts)
        
    KeypointMatching._find_homography = _safe_find_homography
except (ImportError, AttributeError) as e:
    # AttributeError if Airtest renames the private _find_homography on upgrade;
    # log so an unpatched state is diagnosable instead of resurfacing as a raw cv2 crash.
    _logger.warning("Could not patch _find_homography: %s", e)
# -----------------------------------------------------------------------------

def _get_screen_size():
    try:
        w = G.DEVICE.display_info["width"]
        h = G.DEVICE.display_info["height"]
        return w, h
    except Exception:
        return 720, 1280

# Re-exports from extracted modules
from pixon.common.matching import partial_search, wait_exists, wait_not_exists, wait_exists_pos, default_img_setup, SmartTemplate
from pixon.common.ocr import find_all_text, find_all_text_with_conf, OcrLine, is_text_present, _get_ocr, detect_level_badge, read_level_from_badge
from pixon.common.logging_utils import log_info, log_warning, log_error, record_failure, StepError

def try_touch_and_wait(img_or_pos, wait_time=3, area=None):
    if isinstance(img_or_pos, Template):
        img_or_pos = default_img_setup(img_or_pos)
        coord = wait_exists(img_or_pos, 3, area=area)
    else:
        coord = img_or_pos
    if coord:
        touch(coord)
        sleep(wait_time)
        return True
    log_info(f"Fail to touch at {img_or_pos}")
    return False

def try_touch_and_hold(img_or_pos, hold_time=1, area=None):
    if isinstance(img_or_pos, Template):
        img_or_pos = default_img_setup(img_or_pos)
        coord = wait_exists(img_or_pos, 3, area=area)
    else:
        coord = img_or_pos
    if coord:
        touch(coord, duration=hold_time)
        sleep(0.5)
        return True
    log_info(f"Fail to touch at {img_or_pos}")
    return False

def try_touch(img_or_pos, area=None):
    if isinstance(img_or_pos, Template):
        img_or_pos = default_img_setup(img_or_pos)
        coord = partial_search(img_or_pos, area=area)
    else:
        coord = img_or_pos
    if coord:
        touch(coord)
        return True
    log_info(f"Fail to touch at {img_or_pos}")
    return False

def zoom_in(center=None):
    pinch("in", center)
    sleep(0.5)

def zoom_out(center=None):
    pinch("out", center)
    sleep(0.5)

def swipe_up(start=None):
    w, h = _get_screen_size()
    if start is None:
        start = (int(w * 0.8), int(h * 0.8))
    swipe(start, vector=[0, -0.4], duration=0.5)
    sleep(0.05)

def swipe_down(start=None):
    w, h = _get_screen_size()
    if start is None:
        start = (int(w * 0.8), int(h * 0.2))
    swipe(start, vector=[0, 0.4], duration=0.5)
    sleep(0.05)

def swipe_left(start=None):
    w, h = _get_screen_size()
    if start is None:
        start = (w // 2, h // 2)
    swipe(start, vector=[-0.4, 0], duration=0.5)
    sleep(0.05)

def swipe_right(start=None):
    w, h = _get_screen_size()
    if start is None:
        start = (w // 2, h // 2)
    swipe(start, vector=[0.4, 0], duration=0.5)
    sleep(0.05)

def swipe_from_to(start, end):
    swipe(start, end)
    sleep(0.25)

def restart_app(package_name):
    stop_app(package_name)
    sleep(0.5)
    start_app(package_name)

def launch_app_wait_load_done(package_name, splash_screen_icon):
    G.DEVICE.display_info["orientation"] = 0
    restart_app(package_name)
    sleep(3)
    log_dir = ST.LOG_DIR or "."
    logcat_proc, logcat_file = logcat_to_file(
        package_name, os.path.join(log_dir, "logcat.log")
    )
    try:
        if not wait_exists(splash_screen_icon, timeout=45, interval=1):
            raise RuntimeError("Game load too long — splash screen not found")
        if not wait_not_exists(splash_screen_icon, timeout=90, interval=1):
            raise RuntimeError("Game load too long — splash screen not disappearing")
    finally:
        if logcat_proc:
            logcat_proc.terminate()
            logcat_proc.wait(timeout=4)
        if logcat_file:
            logcat_file.close()

def get_screen() -> np.ndarray:
    return G.DEVICE.snapshot()

def retry(times=3, delay=0.25, exceptions=(Exception,), failure_values=(None,), stable_retry=False):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    result = fn(*args, **kwargs)
                    if result not in failure_values:
                        return result
                except exceptions:
                    if attempt == times:
                        raise
                if stable_retry:
                    from pixon.common.matching import wait_stable
                    wait_stable(timeout=min(delay * 2, 5))
                else:
                    time.sleep(delay)
            return failure_values[0]

        return wrapper

    return decorator

def logcat_to_file(
    package: str, output_file: Union[str, Path], clear=True
) -> Tuple[Optional[subprocess.Popen], Optional[Any]]:
    from airtest.core.android.adb import ADB

    adb: ADB = G.DEVICE.adb
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if clear:
        try:
            adb.cmd("logcat -c")
        except Exception:
            pass
    pid_output = adb.cmd(f"shell pidof {package}").strip()
    if not pid_output:
        _logger.warning(
            "Package '%s' not running. No logcat will be captured.", package
        )
        return None, None
    pids = pid_output.split()
    pid_args = [f"--pid={pid}" for pid in pids]
    cmd = [adb.adb_path] + ["-s", adb.serialno, "logcat"] + pid_args
    log_file = open(output_file, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
    return proc, log_file
