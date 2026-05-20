import subprocess
import time
import signal
import sys
from pathlib import Path


class ScrcpyRecorder:
    def __init__(
        self,
        output: str | Path,
        device: str | None = None,
        max_size: int = 800,
        bit_rate: str = "500k",
        stay_awake: bool = True,
        scrcpy_path: str = "scrcpy",
    ):
        self.output = Path(output)
        self.device = device
        self.max_size = max_size
        self.bit_rate = bit_rate
        self.stay_awake = stay_awake
        self.scrcpy_path = scrcpy_path
        self.proc: subprocess.Popen | None = None

    def start(self):
        if self.proc:
            raise RuntimeError("Scrcpy recording already started")

        cmd = [
            self.scrcpy_path,
            "--record", str(self.output),
            "--no-window",
            "--max-size", str(self.max_size),
            "--video-bit-rate", self.bit_rate,
        ]

        if self.stay_awake:
            cmd.append("--stay-awake")

        if self.device:
            cmd.extend(["--serial", self.device])

        self.output.parent.mkdir(parents=True, exist_ok=True)

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32"
                else 0
            ),
        )

        # Give scrcpy time to initialize stream
        time.sleep(1)

    def stop(self, timeout: float = 5.0):
        if not self.proc:
            return

        try:
            if sys.platform == "win32":
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.proc.send_signal(signal.SIGINT)

            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        finally:
            self.proc = None

        # Ensure file is finalized
        time.sleep(1)

        if not self.output.exists() or self.output.stat().st_size < 1024:
            raise RuntimeError(f"Scrcpy recording failed: {self.output}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
