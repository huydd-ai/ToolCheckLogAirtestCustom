
import json
import time
import base64
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from airtest.core.api import G, sleep
from airtest.core.android.adb import ADB
from pixon.common import wrappers as wrapper
from pixon.common import config as _config
from dataclasses import dataclass
from pixon.common.adb_errors import (
    AdbError, AdbTimeoutError, AdbPermissionError, AdbDeviceOfflineError, AdbCommandFailedError
)

@dataclass
class AdbResult:
    success: bool
    stdout: str
    stderr: str
    error_type: Optional[str] = None

ADB_EXE: Path = Path(ADB.builtin_adb_path())
_ADB: str = str(ADB_EXE)

ACTIVITY: str = f"{_config.GAME_PACKAGE}/com.pixon.studio.CustomUnityActivity"

_tls = threading.local()

_PARAM_KEY_MAP = {"playspeed": "playSpeed"}

SEND_INTENT_MAX_ATTEMPTS = 3      # 1 send + 2 retries
SEND_INTENT_UP_TIMEOUT = 30.0     # seconds to wait for app process after each send


def set_default_serial(serial: str) -> None:
    # Pass "" to unset (restores G.DEVICE fallback).
    _tls.serial = serial


def _build_payload(**kwargs: Any) -> Dict[str, Any]:
    return {_PARAM_KEY_MAP.get(k, k): v for k, v in kwargs.items() if v is not None}


def run_adb_command(
    cmd: list, timeout: int = 30, serial: str = "", check: bool = True, log_cmd: Optional[str] = None
) -> AdbResult:
    """Run an adb command with explicit error handling and retry boundaries."""
    if not serial:
        serial = _get_serial()
    full_cmd = [_ADB]
    if serial:
        full_cmd += ["-s", serial]
    full_cmd += cmd
    display_cmd = log_cmd if log_cmd is not None else ' '.join(cmd)
    
    max_retries_timeout = 1
    max_retries_offline = 3
    
    timeout_retries = 0
    offline_retries = 0
    
    while True:
        try:
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            if proc.returncode != 0:
                stderr_lower = proc.stderr.lower()
                exc_class: type[AdbError]
                if "device offline" in stderr_lower or "not found" in stderr_lower:
                    if offline_retries < max_retries_offline:
                        offline_retries += 1
                        wrapper.log_warning(f"ADB device offline/not found, retrying ({offline_retries}/{max_retries_offline})...")
                        time.sleep(2)
                        continue
                    error_type = "DeviceOfflineError"
                    msg = f"ADB device offline (code {proc.returncode}): {display_cmd} — {proc.stderr.strip()}"
                    exc_class = AdbDeviceOfflineError
                elif "permission denied" in stderr_lower or "not permitted" in stderr_lower:
                    error_type = "PermissionError"
                    msg = f"ADB permission denied (code {proc.returncode}): {display_cmd} — {proc.stderr.strip()}"
                    exc_class = AdbPermissionError
                else:
                    error_type = "CommandFailedError"
                    msg = f"ADB failed (code {proc.returncode}): {display_cmd} — {proc.stderr.strip()}"
                    exc_class = AdbCommandFailedError
                
                if check:
                    wrapper.record_failure(msg)
                    raise exc_class(msg, cmd=full_cmd, stderr=proc.stderr, returncode=proc.returncode)
                wrapper.log_info(msg)
                return AdbResult(success=False, stdout=proc.stdout, stderr=proc.stderr, error_type=error_type)
                
            wrapper.log_info(f"ADB command success: {display_cmd}")
            return AdbResult(success=True, stdout=proc.stdout, stderr=proc.stderr)
            
        except subprocess.TimeoutExpired:
            if timeout_retries < max_retries_timeout:
                timeout_retries += 1
                wrapper.log_warning(f"ADB timeout, retrying ({timeout_retries}/{max_retries_timeout})...")
                continue
            
            msg = f"ADB no response after {timeout}s: {display_cmd}"
            if check:
                wrapper.record_failure(msg, snapshot=False)
                raise AdbTimeoutError(msg, cmd=full_cmd)
            wrapper.log_info(msg)
            return AdbResult(success=False, stdout="", stderr="Command timed out", error_type="TimeoutError")
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            msg = f"ADB command error: {e} ({display_cmd})"
            if check:
                wrapper.record_failure(msg, snapshot=False)
                raise AdbCommandFailedError(msg, cmd=full_cmd)
            wrapper.log_info(msg)
            return AdbResult(success=False, stdout="", stderr=str(e), error_type="CommandFailedError")



def is_adb_responsive(serial: str = "", timeout: float = 5, retries: int = 2) -> bool:
    """Bounded ADB liveness gate. Uses a DIRECT subprocess (NOT run_adb_command, which now
    raises) and NEVER raises / NEVER records — returns True iff `getprop sys.boot_completed`
    is "1". Makes retries+1 attempts, treating timeout/error as not-responsive."""
    if not serial:
        serial = _get_serial()
    cmd = [_ADB] + (["-s", serial] if serial else []) + ["shell", "getprop", "sys.boot_completed"]
    for _ in range(retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if proc.returncode == 0 and proc.stdout.strip() == "1":
                return True
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return False


def ensure_adb_root(serial: str = "") -> bool:
    """Run `adb root` so shell commands execute natively as root without superuser popup toasts on emulators."""
    res = run_adb_command(["root"], serial=serial, check=False)
    return res.success


def _run_shell_as_root(cmd_str: str, serial: str = "") -> AdbResult:
    """Run a shell command as root without triggering su popup toasts on emulator.

    First runs `adb root` so shell commands execute as root natively without su popup.
    """
    ensure_adb_root(serial)
    res = run_adb_command(["shell", cmd_str], serial=serial, check=False)
    if res.success:
        return res
    # Fallback to su -c only if adb root is unsupported
    return run_adb_command(["shell", "su", "-c", f"'{cmd_str}'"], serial=serial, check=False)


def check_device_health(serial: str = "") -> bool:
    """Validate device is fully online and responsive before testing."""
    if not serial:
        serial = _get_serial()

    ensure_adb_root(serial)

    # 1. State check
    res_state = run_adb_command(["get-state"], serial=serial, check=False)
    if not res_state.success or "device" not in res_state.stdout:
        return False

    # 2. Responsiveness check
    if not is_adb_responsive(serial=serial, timeout=3, retries=1):
        return False

    return True


def _get_serial() -> str:
    tls_serial = getattr(_tls, "serial", "")
    if tls_serial:
        return tls_serial
    try:
        dev = G.DEVICE
        if dev is not None:
            return getattr(dev, "uuid", "") or ""
    except Exception:
        pass
    return ""


def _is_app_running(serial: str = "") -> bool:
    # Liveness probe: fail fast. A hung adb here stalls every caller (the
    # wait_for_color_trigger poll hits this ~1x/sec), so cap at 3s not the 30s default.
    res = run_adb_command(["shell", "pidof", _config.GAME_PACKAGE], serial=serial, timeout=3, check=False)
    return res.success and res.stdout.strip() != ""


is_app_running = _is_app_running


def wait_for_app_ready(timeout: float = 15, serial: str = "") -> None:
    """Confirm the device is still online AND the game process is alive.

    Meant to run right after the post-cold-start dwell (sleep(30)): cold_start
    only confirms the process at launch, so a crash / ANR / OOM / force-stop
    during the dwell would otherwise surface later as a confusing 'UI element
    not found'. Polls both checks (tolerating a transient adb hiccup) and raises
    AdbError — non-swallowable — the moment the window closes without both true.
    """
    if not serial:
        serial = _get_serial()
    deadline = time.monotonic() + timeout
    last = "no probe ran"
    while True:
        if not check_device_health(serial=serial):
            last = "device offline or adb unresponsive"
        elif not _is_app_running(serial=serial):
            last = "device online but game process not running (crash/ANR/force-stop?)"
        else:
            return
        if time.monotonic() >= deadline:
            break
        sleep(1)
    raise AdbError(f"App not ready {timeout}s after cold start: {last}")


def _send_intent(
    payload: Dict[str, Any],
    *,
    warm_start: bool = False,
    use_base64: bool = False,
    serial: str = "",
) -> bool:
    if not serial:
        serial = _get_serial()
    if payload is None:
        wrapper.log_warning("Payload is None, cannot send intent")
        return False

    json_str: str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    extra_key: str = "jsonBase64" if use_base64 else "json"
    encoded_value: str = (
        base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        if use_base64
        else json_str
    )
    # Device-side POSIX/Android sh single-quote escaping: ' -> '\''
    quoted: str = "'" + encoded_value.replace("'", "'\\''") + "'"
    flag: str = "--activity-single-top " if warm_start else ""
    adb_cmd: str = f"am start {flag}-n {ACTIVITY} --es {extra_key} {quoted}"

    log_quoted: str = "'" + json_str.replace("'", "'\\''") + "'"
    log_cmd: str = f"shell am start {flag}-n {ACTIVITY} --es {extra_key} {log_quoted}"

    # Two confirmations per attempt, because am start exits 0 the instant the shell
    # accepts it — that alone means neither "device got the intent" nor "app started":
    #   1. RECEIVED: am start prints "Error type 3 / Error: Activity class ... does not
    #      exist" to STDERR on a rejected/bad intent while still exiting 0 (so
    #      run_adb_command won't catch it). No "error" in stdout+stderr = device accepted
    #      the intent ("Starting: ..." on cold, "delivered to running top activity" on
    #      warm single-top).
    #   2. STARTED: poll _is_app_running (pidof) until the game process is actually up.
    # If either fails, re-send up to SEND_INTENT_MAX_ATTEMPTS; raise if never confirmed.
    # ponytail: STARTED = process exists, not payload-fields-applied — splash-screen
    # verification lives in wrappers.launch_app_wait_load_done for tests that need it.
    for attempt in range(1, SEND_INTENT_MAX_ATTEMPTS + 1):
        res = run_adb_command(["shell", adb_cmd], serial=serial, timeout=15, log_cmd=log_cmd)  # raises AdbError on adb-call failure
        if "error" in (res.stdout + res.stderr).lower():
            wrapper.log_warning(
                f"_send_intent: am start not accepted (attempt {attempt}/{SEND_INTENT_MAX_ATTEMPTS}): "
                f"{(res.stdout + res.stderr).strip()}",
                snapshot=False,
            )
            continue  # intent rejected by device — re-send, skip the app-up poll
        deadline = time.time() + SEND_INTENT_UP_TIMEOUT
        while time.time() < deadline:
            if _is_app_running(serial=serial):
                return True  # confirmed: received + started
            sleep(1)
        wrapper.log_warning(
            f"_send_intent: app not up after intent (attempt {attempt}/{SEND_INTENT_MAX_ATTEMPTS})",
            snapshot=False,
        )
    # Non-offline AdbError -> runner.py:96 fails fast (no whole-test rerun). NOT
    # log_error, which raises StepError and would be swallowed by `except StepError`.
    raise AdbCommandFailedError(
        f"App {_config.GAME_PACKAGE} did not come up after {SEND_INTENT_MAX_ATTEMPTS} intent sends",
        cmd=log_cmd,
    )


def _force_stop(serial: str = "") -> None:
    # Serial-aware replacement for airtest stop_app(), which always targets
    # G.DEVICE. Routes the force-stop to the same device the intent will hit.
    # Failures are intentionally ignored (airtest stop_app raised on them): a
    # force-stop on a not-running/not-installed app is a no-op, and the launch
    # intent that follows is the operation that actually matters.
    run_adb_command(["shell", "am", "force-stop", _config.GAME_PACKAGE], serial=serial, check=False)


def resume_app(serial: str = "") -> bool:
    """Bring the backgrounded app to the foreground WITHOUT restarting it.

    No force-stop, no clear, no JSON intent — so the running activity instance
    is reused (onNewIntent), not recreated. `--activity-reorder-to-front` pulls
    the existing instance forward; `--activity-single-top` avoids a new instance
    on top. Use after keyevent("HOME") to re-enter the hibernated app. If the
    process was killed while backgrounded this falls back to a plain launch.
    """
    adb_cmd = f"am start --activity-reorder-to-front --activity-single-top -n {ACTIVITY}"
    run_adb_command(["shell", adb_cmd], serial=serial, timeout=15)  # raises AdbError on failure
    return True


def cold_start_with_json(
    payload: Dict[str, Any], *, use_base64: bool = True, serial: str = ""
) -> bool:
    _force_stop(serial=serial)

    clean_payload = dict(payload) if payload else {}
    if clean_payload.pop("clear_data", False):
        run_adb_command(["shell", "pm", "clear", _config.GAME_PACKAGE], serial=serial, check=False)

    started = _send_intent(clean_payload, warm_start=False, use_base64=use_base64, serial=serial)
    if started:
        wait_for_app_ready(serial=serial)
    return started


def cold_start_with_autoplay(
    enabled: bool, playspeed: Optional[int] = None, *, serial: str = ""
) -> bool:
    return cold_start_with_json(
        {"autoplay": enabled, "playSpeed": 6 if enabled else (playspeed if playspeed is not None else 6)},
        use_base64=True,
        serial=serial,
    )


def cold_start_with_combined(
    *,
    level: Optional[int] = None,
    coin: Optional[int] = None,
    booster: Optional[int] = None,
    fakeads: Optional[int] = None,
    autorotate: Optional[int] = None,
    autoplay: Optional[bool] = None,
    playspeed: Optional[int] = None,
    heart: Optional[Union[int, str]] = None,
    hack_iap: bool = True,
    server_sync: bool = False,
    clear_data: bool = True,
    serial: str = "",
) -> bool:
    if clear_data:
        clear_app_data(serial=serial)
    payload = _build_payload(
        level=level, coin=coin, booster=booster, fakeads=fakeads,
        autorotate=autorotate, autoplay=autoplay, playspeed=playspeed, heart=heart,
        hack_iap=hack_iap,
    )
    payload["server_sync"] = server_sync
    return cold_start_with_json(payload, use_base64=True, serial=serial)


def set_hack_iap(enabled: bool, *, serial: str = "") -> bool:
    return warm_send_json({"hack_iap": enabled}, serial=serial)


def cold_start_fresh(*, serial: str = "", **profile: Any) -> bool:
    return cold_start_with_combined(
        server_sync=False, clear_data=True, serial=serial, **profile
    )


def warm_send_json(payload: Dict[str, Any], *, serial: str = "", use_base64: bool = True) -> bool:
    if not _is_app_running(serial=serial):
        wrapper.log_warning("warm_send_json: app not running, skipping")
        return False
    return _send_intent(payload, warm_start=True, use_base64=use_base64, serial=serial)


APP_RESTART_SETTLE_SECONDS = 35.0
APP_UP_TIMEOUT_SECONDS = 30.0


def warm_send_after_restart(
    payload: Dict[str, Any],
    *,
    settle_seconds: float = APP_RESTART_SETTLE_SECONDS,
    app_up_timeout: float = APP_UP_TIMEOUT_SECONDS,
    use_base64: bool = True,
) -> bool:
    sleep(settle_seconds)
    deadline = time.time() + app_up_timeout
    while not _is_app_running() and time.time() < deadline:
        sleep(1)
    if not _is_app_running():
        raise AssertionError(
            "App not running after restart settle; cannot send warm intent"
        )
    return warm_send_json(payload, use_base64=use_base64)


def set_param(key: str, value: Any, *, use_base64: bool = True) -> bool:
    return warm_send_json({key: value}, use_base64=use_base64)


def set_autoplay(
    enabled: bool,
    playspeed: Optional[int] = None,
    *,
    coin: Optional[int] = None,
    heart: Optional[int] = None,
    booster: Optional[Dict[str, int]] = None,
) -> bool:
    payload: Dict[str, Any] = {
        "autoplay": enabled,
        "heart": heart if heart is not None else 5,
        "playSpeed": playspeed if playspeed is not None else 6,
    }
    if coin is not None:
        payload["coin"] = coin
    if booster is not None:
        payload["booster"] = booster
    return warm_send_json(payload, use_base64=True)


def set_level_result(enabled: bool) -> bool:
    return warm_send_json({"set_level_win": enabled}, use_base64=True)


def set_combined(
    *,
    level: Optional[int] = None,
    coin: Optional[int] = None,
    booster: Optional[int] = None,
    fakeads: Optional[int] = None,
    autorotate: Optional[int] = None,
    autoplay: Optional[bool] = None,
    playspeed: Optional[int] = None,
    heart: Optional[Union[int, str]] = None,
    set_level_win: Optional[bool] = None,
) -> bool:
    return warm_send_json(
        _build_payload(
            level=level, coin=coin, booster=booster, fakeads=fakeads,
            autorotate=autorotate, autoplay=autoplay, playspeed=playspeed,
            heart=heart, set_level_win=set_level_win,
        ),
        use_base64=True,
    )


def set_system_time(datetime_str: str, serial: str = "") -> bool:
    run_adb_command(["shell", "settings", "put", "global", "auto_time", "0"], serial=serial, check=False)
    run_adb_command(["shell", "settings", "put", "global", "auto_timezone", "0"], serial=serial, check=False)

    wrapper.log_info("adb shell root date")
    res = _run_shell_as_root(f"date {datetime_str}", serial=serial)
    if not res.success:
        raw = res.stderr.strip()
        if "not permitted" in raw.lower() or "permission denied" in raw.lower():
            wrapper.log_warning(
                "set_system_time failed (no root): the device cannot set the system "
                "clock because no shell has root. Enable the LDPlayer ROOT toggle "
                "(Settings -> other settings -> ROOT permission, then reboot) or use a "
                "userdebug AVD; verify with `adb shell su -c 'id'` returning uid=0. "
                f"Raw: {raw}"
            )
        else:
            wrapper.log_warning(f"set_system_time failed: {raw}")
        return False
    return True


def restore_system_time(serial: str = "") -> bool:
    """Re-enable automatic clock + timezone, undoing set_system_time.

    set_system_time pins a fixed clock by disabling auto_time/auto_timezone.
    Without this restore the emulator clock stays frozen/skewed for every later
    run on the same device image. Best-effort: returns ignored on purpose, a
    restore failure must never mask the real test result.
    """
    run_adb_command(["shell", "settings", "put", "global", "auto_time", "1"], serial=serial, check=False)
    run_adb_command(["shell", "settings", "put", "global", "auto_timezone", "1"], serial=serial, check=False)
    return True


def set_time_relative(hours: float, *, serial: str = "") -> bool:
    res = run_adb_command(["shell", "date", "+%s"], serial=serial)  # raises on failure
    stdout = res.stdout
    if not stdout.strip().isdigit():
        wrapper.log_warning(f"set_time_relative: cannot read device epoch: {stdout!r}")
        return False
        
    device_epoch_before = int(stdout.strip())
    dt_before = datetime.fromtimestamp(device_epoch_before, tz=timezone.utc)
    
    device_epoch = device_epoch_before + int(hours * 3600)
    
    # Format to -u MMDDhhmmYYYY.ss to avoid device timezone bugs or rejected @epoch parsing
    dt = datetime.fromtimestamp(device_epoch, tz=timezone.utc)
    dt_str = dt.strftime("-u %m%d%H%M%Y.%S")
    
    wrapper.log_info(f"adb set_time_relative +{hours}h")
    wrapper.log_info(f"Time before: {dt_before.strftime('%Y-%m-%d %H:%M:%S')} , Time after: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    return set_system_time(dt_str, serial=serial)


def advance_clock(
    hours: Optional[float] = None,
    days: Optional[float] = None,
    *,
    serial: str = "",
) -> bool:
    if hours is not None:
        total_hours = hours
    elif days is not None:
        total_hours = days * 24
    else:
        raise ValueError("advance_clock: pass exactly one of hours= or days=")
    return set_time_relative(total_hours, serial=serial)


def clear_app_data(serial: str = "") -> bool:
    return run_adb_command(["shell", "pm", "clear", _config.GAME_PACKAGE], serial=serial).success


def network_disconnect() -> bool:
    chain = "BLOCK_WAN"

    def _run_iptables(cmd_str: str) -> bool:
        res = _run_shell_as_root(f"iptables -w {cmd_str}")
        if not res.success:
            wrapper.log_error(f"iptables error ({cmd_str}): {res.stderr.strip()}")
            return False
        return True

    try:
        network_reconnect()
        if not _run_iptables(f"-N {chain}"):
            wrapper.log_error("network_disconnect: failed to create iptables BLOCK_WAN chain (no root?)")
            return False
        _run_iptables(f"-A {chain} -d 172.16.1.0/24 -j RETURN")
        _run_iptables(f"-A {chain} -o lo -j RETURN")
        _run_iptables(f"-A {chain} -j DROP")
        if not _run_iptables(f"-I OUTPUT -j {chain}"):
            wrapper.log_error("network_disconnect: failed to inject BLOCK_WAN into OUTPUT")
            return False
        wrapper.log_info("network_disconnect: WAN blocked via iptables")
        return True
    except Exception as e:
        wrapper.log_error(f"network_disconnect exception: {e}")
        return False


def network_reconnect() -> bool:
    chain = "BLOCK_WAN"

    def _run_iptables(cmd_str: str) -> bool:
        res = _run_shell_as_root(f"iptables -w {cmd_str}")
        return res.success

    try:
        _run_iptables(f"-D OUTPUT -j {chain}")
        _run_iptables(f"-F {chain}")
        _run_iptables(f"-X {chain}")
        wrapper.log_info("network_reconnect: WAN restored")
        return True
    except Exception as e:
        wrapper.log_error(f"network_reconnect exception: {e}")
        return False


def disable_wifi() -> bool:
    wrapper.log_info("disable_wifi() is deprecated, use network_disconnect()")
    return network_disconnect()


def enable_wifi() -> bool:
    wrapper.log_info("enable_wifi() is deprecated, use network_reconnect()")
    return network_reconnect()


