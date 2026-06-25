import threading
import time
from pathlib import Path

import cv2
import scrcpy


class ScrcpyRecorder:
    """Record device screen via the scrcpy stream into a single continuous MP4.

    Frame source is the scrcpy-client video stream (no on-device screenrecord,
    no 180s chunking). A background listener keeps the latest frame; a write
    thread paces output by wall-clock so the MP4 plays at real speed even when
    frame arrival is variable. Same interface as OpenCVRecorder.
    """

    def __init__(self, output: str | Path, fps: int = 10, scale: float = 1.0,
                 device: str | None = None, max_fps: int = 0, bitrate: int = 8_000_000,
                 max_width: int = 0, turn_screen_off: bool = False, **kwargs):
        self.output = Path(output)
        self.fps = fps
        self.scale = scale
        self.device = device
        self.max_fps = max_fps
        self.bitrate = bitrate
        self.max_width = max_width
        self.turn_screen_off = turn_screen_off
        self._client = None
        self._serial = None
        self._current_frame = None
        self._stop_event = threading.Event()
        self._disconnected = threading.Event()
        self._write_thread = None
        self._conn_thread = None
        self._writer = None

    def _on_frame(self, frame):
        if frame is not None:
            self._current_frame = frame

    def _on_disconnect(self):
        # scrcpy stream dropped (server killed by app relaunch, device reconnect,
        # etc.). Flag the supervisor to rebuild the client so capture continues.
        self._disconnected.set()

    def _new_client(self):
        client = scrcpy.Client(device=self._serial, max_fps=self.max_fps,
                               bitrate=self.bitrate, max_width=self.max_width)
        client.add_listener(scrcpy.EVENT_FRAME, self._on_frame)
        client.add_listener(scrcpy.EVENT_DISCONNECT, self._on_disconnect)
        return client

    def start(self):
        if self._conn_thread and self._conn_thread.is_alive():
            raise RuntimeError("scrcpy recording already started")

        self._serial = self.device
        if self._serial is None:
            from airtest.core.api import G
            if G.DEVICE and hasattr(G.DEVICE, "adb"):
                self._serial = G.DEVICE.adb.serialno

        self._stop_event.clear()
        self._conn_thread = threading.Thread(target=self._conn_run, daemon=True)
        self._conn_thread.start()
        self._write_thread = threading.Thread(target=self._write_run, daemon=True)
        self._write_thread.start()

    def _conn_run(self):
        """Keep a live scrcpy stream for the whole recording, reconnecting on drop."""
        while not self._stop_event.is_set():
            self._disconnected.clear()
            try:
                self._client = self._new_client()
                self._client.start(threaded=True)
            except Exception as e:
                print(f"[WARN] ScrcpyRecorder: connect failed, retrying: {e}")
                self._stop_event.wait(1.0)
                continue
            if self.turn_screen_off:
                self._screen_off()
            # Stay until the stream drops or we're told to stop.
            while not self._stop_event.is_set() and not self._disconnected.is_set():
                self._stop_event.wait(0.2)
            if self.turn_screen_off and self._stop_event.is_set():
                try:
                    self._client.control.set_screen_power_mode(scrcpy.POWER_MODE_NORMAL)
                except Exception:
                    pass
            try:
                self._client.stop()
            except Exception:
                pass
            if self._disconnected.is_set() and not self._stop_event.is_set():
                print("[WARN] ScrcpyRecorder: stream dropped, reconnecting")
                self._stop_event.wait(0.5)

    def _screen_off(self):
        # Control socket may not be ready the instant start() returns; wait for it.
        for _ in range(25):  # ~5s max
            if self._stop_event.is_set():
                return
            if getattr(self._client, "control_socket", None) is not None:
                try:
                    self._client.control.set_screen_power_mode(scrcpy.POWER_MODE_OFF)
                except Exception as e:
                    print(f"[WARN] ScrcpyRecorder: turn screen off failed: {e}")
                return
            self._stop_event.wait(0.2)

    def _write_run(self):
        start_time = time.time()
        frames_written = 0
        while not self._stop_event.is_set():
            if self._writer is None:
                if self._current_frame is not None:
                    h, w = self._current_frame.shape[:2]
                    if self.scale != 1.0:
                        h, w = int(h * self.scale), int(w * self.scale)
                    # Try MSMF avc1 first for browser compatibility on Windows
                    fourcc = cv2.VideoWriter_fourcc(*'avc1')
                    candidate = cv2.VideoWriter(str(self.output), cv2.CAP_MSMF, fourcc, float(self.fps), (w, h))
                    if candidate.isOpened():
                        self._writer = candidate
                    else:
                        candidate.release()
                        for codec in ['mp4v', 'X264']:
                            fourcc = cv2.VideoWriter_fourcc(*codec)
                            candidate = cv2.VideoWriter(str(self.output), fourcc, float(self.fps), (w, h))
                            if candidate.isOpened():
                                self._writer = candidate
                                break
                            candidate.release()
                    if self._writer is None:
                        print(f"[WARN] ScrcpyRecorder: No working codec found for {self.output}")
                        time.sleep(1)
                    else:
                        start_time = time.time()
                else:
                    time.sleep(0.1)
                continue

            elapsed = time.time() - start_time
            target_frames = int(elapsed * self.fps)
            frames_to_write = target_frames - frames_written

            if frames_to_write > 0 and self._current_frame is not None:
                try:
                    frame_to_write = self._current_frame
                    if self.scale != 1.0:
                        fh, fw = frame_to_write.shape[:2]
                        frame_to_write = cv2.resize(frame_to_write, (int(fw * self.scale), int(fh * self.scale)))

                    for _ in range(frames_to_write):
                        self._writer.write(frame_to_write)
                        frames_written += 1
                except Exception as e:
                    print(f"[WARN] ScrcpyRecorder error writing frame: {e}")

            now = time.time()
            elapsed = now - start_time
            next_frame_time = (frames_written + 1) / float(self.fps)
            sleep_time = next_frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                time.sleep(0.005)

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        if self._conn_thread and self._conn_thread.is_alive():
            self._conn_thread.join(timeout=timeout)
        if self._write_thread and self._write_thread.is_alive():
            self._write_thread.join(timeout=timeout)
        if self._client:
            try:
                self._client.stop()
            except Exception:
                pass
            self._client = None
        if self._writer:
            self._writer.release()
            self._writer = None

        if not self.output.exists() or self.output.stat().st_size < 1024:
            print(f"[WARN] scrcpy recording failed or is too small: {self.output}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
