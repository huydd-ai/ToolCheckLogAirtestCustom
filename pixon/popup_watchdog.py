import threading
import time
from pixon.common import wrappers as wrapper
from pixon.pages.base_page import get_template

class PopupWatchdog:
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread = None
        self.btn_close = get_template("system_function/btn_close.png", (0.365, -0.861))

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            wrapper.log_warning("Popup watchdog is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        wrapper.log_info("Popup watchdog started.")

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        wrapper.log_info("Popup watchdog stopped.")

    def _run(self):
        # NOTE: This thread cannot see TLS serial set via adb_utils.set_default_serial.
        # Before wiring this into any test, pass an explicit serial to the touch path
        # and verify no concurrent ADB traffic with the main test thread.
        while not self._stop_event.is_set():
            try:
                if result := wrapper.partial_search(self.btn_close):
                    wrapper.log_info("Popup watchdog: detected popup, closing...")
                    from pixon.common.matching import _extract_pos
                    pos = _extract_pos(result)
                    if pos:
                        wrapper.G.DEVICE.touch(pos) # ponytail: avoided triple-searching by passing coordinate directly
                        wrapper.log_info("Popup watchdog: closed popup.")
            except Exception as e:
                wrapper.log_warning(f"Popup watchdog error: {e}")

            time.sleep(self.poll_interval)
