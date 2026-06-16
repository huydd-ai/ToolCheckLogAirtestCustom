import time as _time
from pathlib import Path
from typing import Any, Callable

from airtest.core.settings import Settings as ST
from pixon.common import test_flow as _tf

_steps: list[dict] = []
_orig_run_step = _tf.run_step


def _latest_screenshot() -> str | None:
    """Find the most recently modified .jpg/.png in ST.LOG_DIR."""
    d = Path(ST.LOG_DIR) if ST.LOG_DIR else None
    if not d or not d.exists():
        return None
    imgs = sorted(list(d.glob("*.jpg")) + list(d.glob("*.png")), key=lambda p: p.stat().st_mtime)
    return imgs[-1].name if imgs else None


def _emit_step_log(name: str, action_name: str, start: float, end: float, ret: Any, traceback: str | None) -> None:
    """Emit an Airtest NDJSON 'function' entry so LogToHtml can show the step in report.html."""
    try:
        from airtest.core.helper import G as _G
        data: dict[str, Any] = {
            "name": name,
            "call_args": {"action": action_name},
            "start_time": start,
            "end_time": end,
            "ret": ret,
        }
        if traceback is not None:
            data["traceback"] = traceback
        _G.LOGGER.log("function", depth=1, data=data)
    except Exception:
        pass


def _snapshot_step(name: str) -> str | None:
    """Take an Airtest snapshot tied to the step name so HTML binds an image to the step."""
    try:
        from airtest.core.api import snapshot as _snap
        result = _snap(msg=name)
        if isinstance(result, dict):
            return result.get("screen")
        return None
    except Exception:
        return None


def _hooked_run_step(name: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Intercept run_step calls to capture step name, action, status, screenshot, and error."""
    action_name = getattr(action, "__name__", str(action))
    step = {
        "name": name,
        "action": action_name,
        "status": None,
        "screenshot": None,
        "behaviour": None,
        "duration": None,
    }
    start = _time.time()
    try:
        result = _orig_run_step(name, action, *args, **kwargs)
        screen_path = _snapshot_step(name)
        step["status"] = "PASS"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=None)
        return result
    except Exception as exc:
        screen_path = _snapshot_step(name)
        step["status"] = "FAIL"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["behaviour"] = str(exc)
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=str(exc))
        raise


def patch_run_step():
    _tf.run_step = _hooked_run_step


def clear_steps():
    _steps.clear()


def get_steps() -> list[dict]:
    return _steps
