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
    chipset: str = "unknown"
    model_name: str = "unknown"
    ram_gb: float = 0.0
    net_profile: str = "WiFi"
    is_healthy: bool = True

_logger = logging.getLogger("dagster")

class DeviceManager:
    """Manages the pool of Android devices for test sharding."""

    def __init__(self) -> None:
        self.devices: Dict[str, DeviceCaps] = {}

    @property
    def adb_path(self) -> str:
        # ponytail: Reuse airtest's builtin adb binary if possible to avoid conflicts/path issues.
        try:
            from airtest.core.android.adb import ADB
            return ADB.builtin_adb_path()
        except Exception:
            return "adb"

    def discover_devices(self) -> List[str]:
        """Runs adb devices and returns a list of connected serials."""
        try:
            result = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True, timeout=3)
            lines = result.stdout.splitlines()
            serials = []
            for line in lines[1:]:
                if "\tdevice" in line:
                    serials.append(line.split("\t")[0])
            return serials
        except subprocess.TimeoutExpired:
            _logger.error("adb devices timed out")
            return []
        except Exception as e:
            _logger.error(f"adb devices failed: {e}")
            return []

    def check_health(self, serial: str) -> Optional[DeviceCaps]:
        """Checks if a device is booted, and probes its capabilities."""
        try:
            adb = self.adb_path

            # Ensure device is in adb root mode to suppress emulator superuser popups
            try:
                subprocess.run([adb, "-s", serial, "root"], capture_output=True, text=True, timeout=1.5)
            except Exception:
                pass
            
            # Get Android version first
            ver_res = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "ro.build.version.release"],
                capture_output=True, text=True, timeout=1.5
            )
            android_version = ver_res.stdout.strip() if ver_res.returncode == 0 else "unknown"

            # Check boot_completed with fallback to version check
            boot_res = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "sys.boot_completed"],
                capture_output=True, text=True, timeout=1.5
            )
            is_booted = (boot_res.returncode == 0 and boot_res.stdout.strip() == "1") or (android_version != "unknown" and len(android_version) > 0)
            if not is_booted:
                _logger.warning(f"Device {serial} is not fully booted.")
                return None

            # Get human-readable device model (e.g. Galaxy S22, Pixel 7)
            model_res = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=1.5
            )
            model_name = model_res.stdout.strip() if model_res.returncode == 0 and model_res.stdout.strip() else "unknown"

            # Get screen resolution
            wm_res = subprocess.run(
                [adb, "-s", serial, "shell", "wm", "size"],
                capture_output=True, text=True, timeout=1.5
            )
            resolution = wm_res.stdout.split(":")[-1].strip() if wm_res.returncode == 0 and ":" in wm_res.stdout else "unknown"

            # Get chipset/platform
            board_res = subprocess.run(
                [adb, "-s", serial, "shell", "getprop", "ro.board.platform"],
                capture_output=True, text=True, timeout=1.5
            )
            chipset = board_res.stdout.strip() if board_res.returncode == 0 and board_res.stdout.strip() else model_name

            # Get RAM size
            ram_gb = 0.0
            mem_res = subprocess.run(
                [adb, "-s", serial, "shell", "cat", "/proc/meminfo"],
                capture_output=True, text=True, timeout=1.5
            )
            if mem_res.returncode == 0:
                for line in mem_res.stdout.splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            ram_gb = round(float(parts[1]) / (1024 * 1024), 1)
                        break

            # Fast root check (1.5s timeout) - after adb root, shell runs natively as root without su popup
            is_rooted = False
            try:
                id_res = subprocess.run(
                    [adb, "-s", serial, "shell", "id"],
                    capture_output=True, text=True, timeout=1.5
                )
                is_rooted = id_res.returncode == 0 and ("uid=0(root)" in id_res.stdout or "root" in id_res.stdout)
            except subprocess.TimeoutExpired:
                is_rooted = False

            existing_net = self.devices[serial].net_profile if serial in self.devices else "WiFi"

            caps = DeviceCaps(
                serial=serial,
                is_rooted=is_rooted,
                android_version=android_version,
                resolution=resolution,
                chipset=chipset,
                model_name=model_name,
                ram_gb=ram_gb,
                net_profile=existing_net,
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

    def set_network_emulation_profile(self, serial: str, profile: str) -> bool:
        """Sets active network emulation profile (e.g. WiFi, 3G, 4G, HighLoss)."""
        if serial in self.devices:
            self.devices[serial].net_profile = profile
            _logger.info(f"Set network profile for {serial} -> {profile}")
            return True
        return False

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
