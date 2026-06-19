# dagster/test_opencv_annotator.py
import unittest.mock
from pathlib import Path
import numpy as np
import pytest

from dagster.OpenCVAnnotator import (
    OpenCVAnnotator,
    HAS_CV2 as MODULE_HAS_CV2,
    FRAMES_OPENING,
    FRAMES_PER_STEP,
    FRAMES_CROSSFADE,
    FRAMES_ENDING,
    OUTPUT_FPS,
)


def test_singleton_returns_same_instance():
    a = OpenCVAnnotator()
    b = OpenCVAnnotator()
    assert a is b


def test_reset_clears_state():
    a = OpenCVAnnotator()
    a.reset("prev")
    a.reset("new_name")
    assert a.test_name == "new_name"
    assert len(a.frames) == 0


def test_add_step_ignores_missing_screenshot(tmp_path):
    a = OpenCVAnnotator()
    a.reset()
    a.add_step("step1", "tap", None, "PASS", "12:00")
    assert len(a.frames) == 0


def test_add_step_annotates_frame(tmp_path):
    import cv2
    a = OpenCVAnnotator()
    a.reset()
    img_path = tmp_path / "test.png"
    test_img = np.zeros((100, 200, 3), dtype=np.uint8)
    cv2.imwrite(str(img_path), test_img)
    a.add_step("step1", "tap", str(img_path), "PASS", "12:00")
    assert len(a.frames) == 1
    assert a.frames[0].shape[:2] == (100, 200)


def test_add_step_ignores_bad_path(tmp_path):
    a = OpenCVAnnotator()
    a.reset()
    a.add_step("step1", "tap", str(tmp_path / "nonexistent.png"), "PASS", "12:00")
    assert len(a.frames) == 0


def test_finalize_no_frames_returns_none(tmp_path):
    a = OpenCVAnnotator()
    a.reset()
    result = a.finalize("PASS", tmp_path / "out.mp4")
    assert result is None


def test_finalize_produces_valid_mp4(tmp_path):
    import cv2
    a = OpenCVAnnotator()
    a.reset("my_test")
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), np.zeros((100, 200, 3), dtype=np.uint8))
    a.add_step("step1", "tap", str(img_path), "PASS", "12:00")
    a.add_step("step2", "swipe", str(img_path), "FAIL", "12:01")

    out = tmp_path / "steps.mp4"
    result = a.finalize("FAIL", out)
    assert result == out
    assert out.exists() and out.stat().st_size > 100

    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    expected = FRAMES_OPENING + 2 * FRAMES_PER_STEP + 1 * FRAMES_CROSSFADE + FRAMES_ENDING
    assert total_frames == expected
    assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 200
    assert int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 100
    assert cap.get(cv2.CAP_PROP_FPS) == pytest.approx(OUTPUT_FPS)
    cap.release()


def test_finalize_lots_of_steps(tmp_path):
    import cv2
    a = OpenCVAnnotator()
    a.reset()
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), np.zeros((50, 80, 3), dtype=np.uint8))
    for i in range(10):
        a.add_step(f"s{i}", "tap", str(img_path), "PASS" if i % 2 == 0 else "FAIL", f"{i:02d}:00")

    out = tmp_path / "steps.mp4"
    result = a.finalize("FAIL", out)
    assert result == out

    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    expected = FRAMES_OPENING + 10 * FRAMES_PER_STEP + 9 * FRAMES_CROSSFADE + FRAMES_ENDING
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == expected
    cap.release()


@unittest.mock.patch("dagster.OpenCVAnnotator.HAS_CV2", False)
def test_graceful_degradation_no_cv2(tmp_path):
    a = OpenCVAnnotator()
    a.reset()
    a.add_step("step1", "tap", str(tmp_path / "test.png"), "PASS", "12:00")
    assert len(a.frames) == 0
    assert a.finalize("PASS", tmp_path / "out.mp4") is None


def test_nonexistent_output_dir_graceful(tmp_path):
    import cv2
    a = OpenCVAnnotator()
    a.reset()
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), np.zeros((100, 200, 3), dtype=np.uint8))
    a.add_step("s1", "tap", str(img_path), "PASS", "12:00")
    a.add_step("s2", "tap", str(img_path), "PASS", "12:01")
    bad_dir = tmp_path / "nope"
    out = bad_dir / "out.mp4"
    result = a.finalize("PASS", out)
    assert result is None
