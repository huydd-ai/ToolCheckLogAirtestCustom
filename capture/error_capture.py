import logging
from typing import Any

from dagster.capture.log_utils import latest_screenshot

_errors: list[dict[str, Any]] = []

class ErrorCaptureHandler(logging.Handler):
    """Captures ERROR and CRITICAL logs to _errors list."""
    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)

        from dagster.capture.step_capture import get_current as _cur_step
        current_step = _cur_step()

        screen = None
        try:
            from airtest.core.api import snapshot as _snap
            result = _snap(msg=current_step or "error")
            screen = result.get("screen") if isinstance(result, dict) else None
        except Exception:
            pass
        if screen is None:
            screen = latest_screenshot()

        _errors.append({
            "ts": record.created,
            "logger": record.name,
            "step": current_step,
            "msg": msg,
            "screenshot": screen,
        })

def attach_error_handler(logger_name: str = "pixon") -> None:
    """Idempotently attach ErrorCaptureHandler to the target logger."""
    lg = logging.getLogger(logger_name)
    if not any(isinstance(h, ErrorCaptureHandler) for h in lg.handlers):
        lg.addHandler(ErrorCaptureHandler())

def clear_errors() -> None:
    _errors.clear()

def get_errors() -> list[dict[str, Any]]:
    return list(_errors)

def had_errors() -> bool:
    return len(_errors) > 0
