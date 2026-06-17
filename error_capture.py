import logging
import time
from typing import Any

from dagster.log_utils import latest_screenshot

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

        _errors.append({
            "ts": record.created,
            "logger": record.name,
            "msg": msg,
            "screenshot": latest_screenshot(),
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
