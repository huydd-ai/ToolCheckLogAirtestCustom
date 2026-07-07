import os
import logging
from typing import Optional, Tuple
import cv2

from airtest.core.api import G, ST, log
import pixon.common.matching as matching

_logger = logging.getLogger("pixon")
class StepError(RuntimeError):
    pass

def _snapshot_annotated(pos: Optional[Tuple[float, float]]) -> None:
    try:
        screen = G.DEVICE.snapshot()
        if screen is None:
            return
        img = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR) if screen.shape[2] == 4 else screen.copy()
        if pos is not None:
            x, y = int(pos[0]), int(pos[1])
            cv2.circle(img, (x, y), 30, (0, 0, 255), 3)
            cv2.circle(img, (x, y), 5, (0, 0, 255), -1)
        log_dir = ST.LOG_DIR or "."
        fname = f"err_{len(os.listdir(log_dir))}.jpg"
        fpath = os.path.join(log_dir, fname)
        cv2.imwrite(fpath, img)
        if G.LOGGER:
            resolution = [img.shape[1], img.shape[0]]
            G.LOGGER.log(
                "function",
                {
                    "name": "Take Screen and Log",
                    "ret": {"screen": fname, "resolution": resolution},
                },
                depth=2,
            )
    except Exception:
        pass

def record_failure(msg, snapshot=True):
    """Record a failure: write a FAIL: row to the Airtest report and optionally snapshot.
    Does NOT raise — callers (log_error, ADB boundary) raise separately."""
    _logger.error(msg)
    if snapshot:
        _snapshot_annotated(matching._last_match_pos)
        matching._last_match_pos = None
    clean_msg = msg.split("\n")[0]
    G.LOGGER.log(
        "function",
        {
            "name": f"FAIL: {clean_msg}",
            "traceback": msg,
            "log": clean_msg,
            "snapshot": False,
            "call_args": {},
        },
        depth=1,
    )

def log_error(msg, snapshot=True):
    import sys
    exc = sys.exc_info()[1]
    record_failure(msg, snapshot=snapshot)
    raise StepError(msg) from exc

def log_warning(msg, snapshot=True):
    _logger.warning(msg)
    log(f"WARNING: {msg}", snapshot=snapshot)

def log_info(msg, snapshot=True):
    _logger.info(msg)
    log(f"[INFO] {msg}", snapshot=snapshot)
