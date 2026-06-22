import threading
import time
from pathlib import Path
import cv2

class OpenCVRecorder:
    def __init__(self, output: str | Path, fps: int = 10, **kwargs):
        self.output = Path(output)
        self.fps = fps
        self._thread = None
        self._stop_event = threading.Event()
        self._writer = None

    def start(self):
        if getattr(self, '_capture_thread', None) and self._capture_thread.is_alive():
            raise RuntimeError("OpenCV recording already started")
            
        self._stop_event.clear()
        
        from pixon.common import wrappers as wrapper
        screen = wrapper.get_screen()
        if screen is None:
            time.sleep(1)
            screen = wrapper.get_screen()
            
        if screen is None:
            print("[WARN] OpenCVRecorder: Could not get initial screen in start(), will retry in thread.")

        self._current_frame = None
        self._capture_thread = threading.Thread(target=self._capture_run, daemon=True)
        self._write_thread = threading.Thread(target=self._write_run, daemon=True)
        self._capture_thread.start()
        self._write_thread.start()

    def _capture_run(self):
        from pixon.common import wrappers as wrapper
        while not self._stop_event.is_set():
            try:
                screen = wrapper.get_screen()
                if screen is not None:
                    self._current_frame = screen
            except Exception:
                pass
            # Small sleep to yield CPU, get_screen is already blocking/heavy
            time.sleep(0.01)

    def _write_run(self):
        start_time = time.time()
        frames_written = 0
        while not self._stop_event.is_set():
            if self._writer is None:
                if self._current_frame is not None:
                    h, w = self._current_frame.shape[:2]
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
                        print(f"[WARN] OpenCVRecorder: No working codec found for {self.output}")
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
                    for _ in range(frames_to_write):
                        self._writer.write(self._current_frame)
                        frames_written += 1
                except Exception as e:
                    print(f"[WARN] OpenCVRecorder error writing frame: {e}")

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
        if getattr(self, '_capture_thread', None) and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=timeout/2)
        if getattr(self, '_write_thread', None) and self._write_thread.is_alive():
            self._write_thread.join(timeout=timeout/2)
        if self._writer:
            self._writer.release()
            self._writer = None

        if not self.output.exists() or self.output.stat().st_size < 1024:
            print(f"[WARN] OpenCV recording failed or is too small: {self.output}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
