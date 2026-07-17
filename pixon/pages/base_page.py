# pages/base_page.py
from pixon.common.matching import _silent_match
from pathlib import Path
from pixon.common import wrappers as wrapper
from airtest.core.api import (
    Template,
    touch,
    sleep,
    keyevent,
    snapshot,
    text as airtest_text,
    G,
)
import time
from typing import Optional, Tuple, Any, List, Union

IMAGE_DIR = Path(__file__).resolve().parent / "images"


def get_template(
    relative_path: str,
    record_pos: Tuple[float, float],
    resolution: Optional[Tuple[int, int]] = None,
    threshold: Optional[float] = None,
    **kwargs: Any
) -> Template:
    if resolution is None:
        resolution = (720, 1280)
    if threshold is not None:
        kwargs["threshold"] = threshold
    return Template(
        str(IMAGE_DIR / relative_path), record_pos=record_pos, resolution=resolution, **kwargs
    )


class BasePage:
    """
    Base class for all page objects.
    
    Standardized Error Handling Contract:
    - Search functions (wait_for_element, wait_for_text): Return bool/None. Never raise.
    - Action functions (tap, long_tap, swipe): Return bool (False on failure). Never raise.
    - Assert functions (assert_element_exists, assert_text_present): Raise AssertionError on failure.
    - Logging: wrapper.log_info and wrapper.log_warning never raise. wrapper.log_error raises StepError.
    """
    def __init__(self, device: Any = None) -> None:
        self.device = device

    def get_screen_size(self) -> Tuple[int, int]:
        info = G.DEVICE.display_info
        return info["width"], info["height"]

    def wait_for_element(
        self, template: Union[Template, List[Template], Tuple[Template, ...]], timeout: float = 5
    ) -> bool:
        if isinstance(template, (list, tuple)):
            start = time.time()
            while time.time() - start < timeout:
                screen = G.DEVICE.snapshot()
                for t in template:
                    if _silent_match(t, screen):
                        return True
                sleep(0.5)
            return False
        return bool(wrapper.wait_exists(template, timeout=timeout))

    def wait_for_text(self, text: str, area: Optional[Union[Tuple[int, int, int, int], List[int]]] = None, timeout: float = 5) -> bool:
        start: float = time.time()
        from pixon.common.matching import wait_stable
        wait_stable(area=area, timeout=min(timeout, 5))
        while time.time() - start < timeout:
            if wrapper.is_text_present(text, area):
                return True
            # ponytail: OCR pass costs 0.3-1s and pegs all 4 threads; 0.5s gives it room to breathe
            sleep(0.5)
        return False

    def tap(self, element: Union[Template, Tuple[int, int]]) -> bool:
        if isinstance(element, Template):
            return wrapper.try_touch(element)
        try:
            touch(element)
            return True
        except Exception as exc:
            wrapper.log_warning(f"tap: failed to touch {element!r}: {exc}")
            return False

    def double_tap(self, element: Union[Template, Tuple[int, int]]) -> bool:
        success = self.tap(element)
        sleep(0.05)
        return success and self.tap(element)

    def long_tap(self, element: Union[Template, Tuple[int, int]], duration: float = 2) -> bool:
        if isinstance(element, Template):
            return wrapper.try_touch_and_hold(element, hold_time=duration)
        try:
            touch(element, duration=duration)
            return True
        except Exception as exc:
            wrapper.log_warning(f"long_tap: failed to touch {element!r}: {exc}")
            return False

    def swipe(self, direction: str, duration: float = 0.5) -> None:
        if direction == "up":
            wrapper.swipe_up()
        elif direction == "down":
            wrapper.swipe_down()
        elif direction == "left":
            wrapper.swipe_left()
        elif direction == "right":
            wrapper.swipe_right()
        else:
            raise ValueError(f"Unsupported direction: {direction}")

    def zoom_in(self, center: Optional[Tuple[int, int]] = None) -> None:
        wrapper.zoom_in(center)

    def zoom_out(self, center: Optional[Tuple[int, int]] = None) -> None:
        wrapper.zoom_out(center)

    def input_text(self, text: str, confirm: bool = True) -> None:
        airtest_text(text, enter=confirm)

    def clear_input(self, element: Union[Template, Tuple[int, int]]) -> None:
        self.tap(element)
        keyevent("v2_CONTROL+A")
        keyevent("v2_DELETE")

    def take_screenshot(self, name: Optional[str] = None) -> None:
        if not name:
            name = f"screenshot_{int(time.time())}.png"
        snapshot(filename=name)

    def handle_popup(self, close_button: Template, timeout: float = 1.5) -> bool:
        if self.wait_for_element(close_button, timeout):
            return self.tap(close_button)
        return False

    def assert_element_exists(self, template: Union[Template, List[Template], Tuple[Template, ...]], msg: Optional[str] = None) -> None:
        if not self.wait_for_element(template):
            raise AssertionError(msg or f"Element not found: {template}")

    def assert_text_present(self, text: str, area: Optional[Union[Tuple[int, int, int, int], List[int]]] = None, msg: Optional[str] = None) -> None:
        if not self.wait_for_text(text, area):
            raise AssertionError(msg or f"Text not found: '{text}'")
