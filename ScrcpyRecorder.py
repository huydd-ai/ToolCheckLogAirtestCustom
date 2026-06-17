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
        max_size: int = 0,
        bit_rate: str = "8M",
        max_fps: int = 240,
        video_codec: str = "h264",
        video_codec_options: str = "",
        turn_screen_off: bool = False,
        stay_awake: bool = True,
        scrcpy_path: str = "scrcpy",
    ):
        self.output = Path(output)
        self.device = device
        self.max_size = max_size
        self.bit_rate = bit_rate
        self.max_fps = max_fps
        self.video_codec = video_codec
        self.video_codec_options = video_codec_options
        self.turn_screen_off = turn_screen_off
        self.stay_awake = stay_awake
        self.scrcpy_path = scrcpy_path
        self.proc: subprocess.Popen | None = None

    def start(self):
        if self.proc:
            raise RuntimeError("Scrcpy recording already started")

        cmd = [
            self.scrcpy_path,
            "--record", str(self.output),
            "--no-playback",
            "--video-bit-rate", self.bit_rate,
            "--max-fps", str(self.max_fps),
            "--video-codec", self.video_codec,
        ]

        if self.video_codec_options:
            cmd.extend(["--video-codec-options", self.video_codec_options])

        if self.max_size > 0:
            cmd.extend(["--max-size", str(self.max_size)])

        if self.turn_screen_off:
            cmd.append("--turn-screen-off")

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
            time.sleep(1)
        finally:
            self.proc = None

        if not self.output.exists() or self.output.stat().st_size < 1024:
            raise RuntimeError(f"Scrcpy recording failed: {self.output}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
