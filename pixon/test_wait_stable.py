"""Offline self-check for wait_stable and retry(stable_retry).
Run: python pixon/common/test_wait_stable.py"""

import os
import time
import numpy as np


class _FakeDevice:
    frames = []  # list of (np.ndarray, delay) | np.ndarray
    idx = 0

    @classmethod
    def snapshot(cls):
        if cls.idx >= len(cls.frames):
            cls.idx = 0  # loop for unbounded reads
        entry = cls.frames[cls.idx]
        cls.idx += 1
        if isinstance(entry, tuple):
            time.sleep(entry[1])
            return entry[0]
        return entry


def _patch_device():
    import pixon.common.matching as m
    m.G.DEVICE = _FakeDevice()


def _reset():
    _FakeDevice.frames = []
    _FakeDevice.idx = 0


def test_wait_stable_identical_frames():
    _reset()
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    _FakeDevice.frames = [img] * 6
    _patch_device()

    from pixon.common.matching import wait_stable
    result = wait_stable(timeout=5, settle_interval=0.01, stable_required=3)
    assert result is True, f"expected True for identical frames, got {result}"
    print("test_wait_stable_identical_frames: passed")


def test_wait_stable_never_stable():
    _reset()
    a = np.full((100, 100, 3), 0, dtype=np.uint8)
    b = np.full((100, 100, 3), 255, dtype=np.uint8)
    _FakeDevice.frames = [a, b]  # alternates, never 3 identical in a row
    _patch_device()

    from pixon.common.matching import wait_stable
    result = wait_stable(timeout=0.5, settle_interval=0.01, stable_required=3)
    assert result is False, f"expected False for never-stable frames, got {result}"
    print("test_wait_stable_never_stable: passed")


def test_wait_stable_eventually_stable():
    _reset()
    img_stable = np.full((100, 100, 3), 128, dtype=np.uint8)
    imgs = [np.full((100, 100, 3), i, dtype=np.uint8) for i in range(5)] + [img_stable] * 6
    _FakeDevice.frames = imgs
    _patch_device()

    from pixon.common.matching import wait_stable
    result = wait_stable(timeout=5, settle_interval=0.01, stable_required=3)
    assert result is True, f"expected True for eventually stable frames, got {result}"
    print("test_wait_stable_eventually_stable: passed")


def test_retry_stable_flag_present():
    from pixon.common.wrappers import retry

    @retry(times=2, delay=0.01, stable_retry=True)
    def always_fails():
        raise ValueError("expected")

    try:
        always_fails()
        assert False, "expected ValueError"
    except ValueError:
        pass
    print("test_retry_stable_flag_present: passed")


if __name__ == "__main__":
    test_wait_stable_identical_frames()
    test_wait_stable_never_stable()
    test_wait_stable_eventually_stable()
    test_retry_stable_flag_present()
    print("test_wait_stable: all checks passed")
