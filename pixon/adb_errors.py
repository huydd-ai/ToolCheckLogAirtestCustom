"""Dedicated ADB failure type. Deliberately NOT a StepError — existing `except StepError`
sites (game_page._activate_with_retry, go_home_clean) must not catch these, or they would
swallow / re-wrap the failure and defeat fail-on-ADB-error. Raised by run_adb_command(check=True);
the message carries the adb cmd + stderr."""

from typing import Optional, Union

class AdbError(Exception):
    """Exception raised for ADB command failures or timeouts.
    
    Attributes:
        message (str): Formatted error message containing cmd and stderr.
        cmd (str | list, optional): The command that failed.
        stderr (str, optional): The captured stderr output.
        returncode (int, optional): The exit code of the process.
    """
    
    def __init__(self, message: str, cmd: Optional[Union[str, list]] = None, stderr: Optional[str] = None, returncode: Optional[int] = None):
        super().__init__(message)
        self.cmd = cmd
        self.stderr = stderr
        self.returncode = returncode


class AdbTimeoutError(AdbError):
    """Raised when an ADB command times out."""
    pass


class AdbPermissionError(AdbError):
    """Raised when ADB returns permission denied."""
    pass


class AdbDeviceOfflineError(AdbError):
    """Raised when the target ADB device is offline or not found."""
    pass


class AdbCommandFailedError(AdbError):
    """Raised for any other ADB command failure (non-zero exit code)."""
    pass
