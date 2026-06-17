import logging
import sys

LOG_LEVEL: int = logging.DEBUG

def setup_console_logging(level: int = logging.INFO) -> None:
    """Attach a stdout StreamHandler to Airtest's loggers so steps print to CLI."""
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.setLevel(level)
    for logger_name in ("airtest", "poco"):
        lg = logging.getLogger(logger_name)
        lg.setLevel(level)
        if not any(isinstance(h, logging.StreamHandler) for h in lg.handlers):
            lg.addHandler(handler)
        lg.propagate = False

from pathlib import Path
from airtest.core.settings import Settings as ST

def latest_screenshot() -> str | None:
    """Find the most recently modified .jpg/.png in ST.LOG_DIR."""
    d = Path(ST.LOG_DIR) if ST.LOG_DIR else None
    if not d or not d.exists():
        return None
    imgs = sorted(list(d.glob("*.jpg")) + list(d.glob("*.png")), key=lambda p: p.stat().st_mtime)
    return imgs[-1].name if imgs else None
