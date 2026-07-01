from datetime import datetime as _datetime
import time as _time
from pathlib import Path
from typing import Any, Callable

from airtest.core.settings import Settings as ST
from pixon.common import test_flow as _tf

_steps: list[dict] = []
_current: str | None = None   # in-flight: set while run_step executes
_last: str | None = None       # persistent: last step that ran, never cleared
_orig_run_step = _tf.run_step

from dagster.capture.log_utils import latest_screenshot as _latest_screenshot
from dagster.recording.OpenCVAnnotator import OpenCVAnnotator as _Annotator
import pixon.common.logging_utils as _lu
_orig_log_info = _lu.log_info


def get_current() -> str | None:
    """Return in-flight step name, or last-ran step name if between steps."""
    return _current or _last


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
    global _current, _last
    _current = name
    _last = name
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
    print(f"[{_datetime.now().strftime('%H:%M:%S')}] RUNNING: {name} ({action_name})", flush=True)
    try:
        result = _orig_run_step(name, action, *args, **kwargs)
        screen_path = _snapshot_step(name)
        step["status"] = "PASS"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        print(f"[{_datetime.now().strftime('%H:%M:%S')}] PASS: {name} ({step['duration']}s)", flush=True)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=None)
        return result
    except Exception as exc:
        screen_path = _snapshot_step(name)
        step["status"] = "FAIL"
        step["screenshot"] = screen_path or _latest_screenshot()
        step["behaviour"] = str(exc)
        step["duration"] = round(_time.time() - start, 2)
        _steps.append(step)
        print(f"[{_datetime.now().strftime('%H:%M:%S')}] FAIL: {name} ({step['duration']}s)", flush=True)
        _emit_step_log(name, action_name, start, _time.time(), ret=screen_path, traceback=str(exc))
        raise
    finally:
        _current = None   # clear in-flight; _last stays
        try:
            _Annotator().add_step(
                name=step["name"],
                action=step["action"],
                screenshot_path=step.get("screenshot"),
                status=step.get("status") or "PASS",
                timestamp=_datetime.now().strftime("%H:%M:%S"),
            )
        except Exception:
            pass


def _hooked_log_info(msg: str, snapshot: bool = True) -> None:
    _orig_log_info(msg, snapshot=snapshot)
    
    msg_strip = msg.strip()
    # Intercept milestones to show in Tester View
    if msg_strip.startswith("Start:") or msg_strip.startswith("End:") or msg_strip.startswith("Result:") or msg_strip.startswith("[Step") or "100% complete" in msg_strip:
        step = {
            "name": msg,
            "action": "log_info",
            "status": "INFO",
            "screenshot": _latest_screenshot() if snapshot else None,
            "behaviour": None,
            "duration": 0.0,
        }
        _steps.append(step)
        
        try:
            _Annotator().add_step(
                name=step["name"],
                action=step["action"],
                screenshot_path=step.get("screenshot"),
                status=step.get("status"),
                timestamp=_datetime.now().strftime("%H:%M:%S"),
            )
        except Exception:
            pass

def patch_run_step():
    _tf.run_step = _hooked_run_step
    _lu.log_info = _hooked_log_info


def clear_steps():
    global _current, _last
    _current = None
    _last = None
    _steps.clear()


def get_steps() -> list[dict]:
    return _steps
