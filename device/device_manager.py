import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class DeviceCaps:
    serial: str
    is_rooted: bool
    android_version: str
    resolution: str
    is_healthy: bool = True

_logger = logging.getLogger("dagster")

class DeviceManager:
    """Manages the pool of Android devices for test sharding."""

    def __init__(self) -> None:
        self.devices: Dict[str, DeviceCaps] = {}

    def discover_devices(self) -> List[str]:
        """Runs adb devices and returns a list of connected serials."""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            lines = result.stdout.splitlines()
            serials = []
            for line in lines[1:]:
                if "\tdevice" in line:
                    serials.append(line.split("\t")[0])
            return serials
        except subprocess.TimeoutExpired:
            _logger.error("adb devices timed out")
            return []

    def check_health(self, serial: str) -> Optional[DeviceCaps]:
        """Checks if a device is booted, and probes its capabilities."""
        try:
            # Check boot_completed
            boot_res = subprocess.run(
                ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                capture_output=True, text=True, timeout=5
            )
            if boot_res.returncode != 0 or boot_res.stdout.strip() != "1":
                _logger.warning(f"Device {serial} is not fully booted.")
                return None

            # Get Android version
            ver_res = subprocess.run(
                ["adb", "-s", serial, "shell", "getprop", "ro.build.version.release"],
                capture_output=True, text=True, timeout=5
            )
            android_version = ver_res.stdout.strip() if ver_res.returncode == 0 else "unknown"

            # Get screen resolution
            wm_res = subprocess.run(
                ["adb", "-s", serial, "shell", "wm", "size"],
                capture_output=True, text=True, timeout=5
            )
            resolution = wm_res.stdout.split(":")[-1].strip() if wm_res.returncode == 0 and ":" in wm_res.stdout else "unknown"

            # Check root
            su_res = subprocess.run(
                ["adb", "-s", serial, "shell", "su", "-c", "id"],
                capture_output=True, text=True, timeout=5
            )
            is_rooted = su_res.returncode == 0 and "uid=0(root)" in su_res.stdout

            caps = DeviceCaps(
                serial=serial,
                is_rooted=is_rooted,
                android_version=android_version,
                resolution=resolution,
                is_healthy=True
            )
            self.devices[serial] = caps
            return caps

        except subprocess.TimeoutExpired:
            _logger.warning(f"Device {serial} timed out during health check.")
            return None
        except Exception as e:
            _logger.warning(f"Device {serial} health check failed: {e}")
            return None

    def get_healthy_devices(self) -> List[DeviceCaps]:
        """Discovers and returns a list of healthy devices."""
        serials = self.discover_devices()
        healthy_caps = []
        for serial in serials:
            caps = self.check_health(serial)
            if caps:
                healthy_caps.append(caps)
        return healthy_caps

device_manager = DeviceManager()
