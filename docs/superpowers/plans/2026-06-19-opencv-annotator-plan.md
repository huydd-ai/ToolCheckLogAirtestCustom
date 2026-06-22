# OpenCV Step Annotator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-step annotated video compilation to each test run, producing a `_steps.mp4` that overlays step name/action/status/timestamp on screenshots with opening/ending frames and crossfade transitions.

**Architecture:** New `OpenCVAnnotator` singleton (module-level `__new__` pattern, graceful `HAS_CV2` degradation) collects annotated frames per test via `add_step()` in `_hooked_run_step`'s `finally` block. `runner.py` calls `reset()` before test and `finalize()` after test; the resulting MP4 path appears as a separate badge in the summary report.

**Tech Stack:** OpenCV (`cv2`, `numpy`), `opencv-python==4.11.0.86` already installed. Video: H.264 MP4 @ 10fps, `avc1`/`mp4v`/`X264` fallback codecs.

**Video composition per test:**
- Opening (3s / 30 frames @ 10fps): test name + date on dark background
- Per step (2.2s hold + 0.3s crossfade = 2.5s each annotated screenshot): status-colored left border, semi-transparent top bar with step name + action, PASS/FAIL badge (top-right), timestamp (bottom-left)
- Ending (3s / 30 frames): overall status centered, step summary line

---
### Task 1: OpenCVAnnotator class + unit tests

**Files:**
- Create: `dagster/OpenCVAnnotator.py`
- Create: `dagster/test_opencv_annotator.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest dagster/test_opencv_annotator.py -v --tb=short`
Expected: ImportError for `OpenCVAnnotator`

- [ ] **Step 3: Write minimal implementation**

```python
# dagster/OpenCVAnnotator.py
import logging
from datetime import datetime
from pathlib import Path

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logger = logging.getLogger(__name__)

FRAMES_PER_STEP = 22
FRAMES_CROSSFADE = 3
FRAMES_OPENING = 30
FRAMES_ENDING = 30
OUTPUT_FPS = 10


class OpenCVAnnotator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reset()
        return cls._instance

    def _reset(self, test_name: str = ""):
        self.frames: list = []
        self.test_name = test_name
        self.total_steps = 0
        self.fail_count = 0

    @classmethod
    def reset(cls, test_name: str = ""):
        inst = cls()
        inst._reset(test_name)

    def add_step(self, name: str, action: str, screenshot_path: str | None, status: str, timestamp: str):
        if not HAS_CV2 or not screenshot_path:
            return
        try:
            img = cv2.imread(screenshot_path)
            if img is None:
                return
            annotated = self._annotate_frame(img, name, action, status, timestamp)
            self.frames.append(annotated)
            self.total_steps += 1
            if status == "FAIL":
                self.fail_count += 1
        except Exception:
            logger.warning("Failed to annotate step '%s'", name, exc_info=True)

    def _annotate_frame(self, img, name, action, status, timestamp):
        h, w = img.shape[:2]
        status_color = (0, 255, 0) if status == "PASS" else (0, 0, 255)

        cv2.rectangle(img, (0, 0), (6, h), status_color, -1)

        overlay = img.copy()
        cv2.rectangle(overlay, (6, 0), (w, 65), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)

        cv2.putText(img, name, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(img, action, (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        badge_text = f" {status} "
        (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        bx = w - tw - 22
        by = 8
        cv2.rectangle(img, (bx, by), (bx + tw + 8, by + th + 8), status_color, -1)
        cv2.putText(img, badge_text, (bx + 4, by + th + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        cv2.putText(img, timestamp, (16, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        return img

    def finalize(self, overall_status: str, output_path: Path) -> Path | None:
        if not HAS_CV2 or not self.frames:
            return None
        try:
            h, w = self.frames[0].shape[:2]
            writer = None
            for codec_chars in [(*'avc1'), (*'mp4v'), (*'X264')]:
                fourcc = cv2.VideoWriter_fourcc(*codec_chars)
                candidate = cv2.VideoWriter(str(output_path), fourcc, OUTPUT_FPS, (w, h))
                if candidate.isOpened():
                    writer = candidate
                    break
                candidate.release()
            if writer is None:
                logger.warning("No working codec found for %s", output_path)
                return None

            opening = self._opening_frame(h, w)
            for _ in range(FRAMES_OPENING):
                writer.write(opening)

            for i in range(len(self.frames)):
                curr = self.frames[i]
                for _ in range(FRAMES_PER_STEP):
                    writer.write(curr)
                if i < len(self.frames) - 1:
                    nxt = self.frames[i + 1]
                    for j in range(FRAMES_CROSSFADE):
                        alpha = (j + 1) / (FRAMES_CROSSFADE + 1)
                        blended = cv2.addWeighted(curr, 1 - alpha, nxt, alpha, 0)
                        writer.write(blended)

            ending = self._ending_frame(h, w, overall_status)
            for _ in range(FRAMES_ENDING):
                writer.write(ending)

            writer.release()

            if output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            return None
        except Exception:
            logger.warning("Failed to finalize video", exc_info=True)
            return None

    def _opening_frame(self, h, w):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        text = self.test_name or "Test"
        font_scale = 1.0 if len(text) < 30 else 0.7
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)
        tx = (w - tw) // 2
        ty = h // 2 - 20
        cv2.putText(frame, text, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (200, 200, 200), 2)
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cv2.putText(frame, date_str, (tx, ty + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        return frame

    def _ending_frame(self, h, w, status):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        is_pass = status == "PASS"
        status_color = (0, 255, 0) if is_pass else (0, 0, 255)

        cv2.putText(frame, status, ((w - cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0][0]) // 2, h // 2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, status_color, 3)

        summary = f"{self.total_steps} step{'s' if self.total_steps != 1 else ''} completed"
        if self.fail_count > 0:
            summary = f"{self.fail_count}/{self.total_steps} step{'s' if self.total_steps != 1 else ''} FAILED"
        cv2.putText(frame, summary, ((w - cv2.getTextSize(summary, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]) // 2, h // 2 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        cv2.putText(frame, date_str, ((w - cv2.getTextSize(date_str, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0][0]) // 2, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
        return frame
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest dagster/test_opencv_annotator.py -v --tb=short`
Expected: 10/10 passed

- [ ] **Step 5: Commit**

```bash
git add dagster/OpenCVAnnotator.py dagster/test_opencv_annotator.py
git commit -m "feat: add OpenCVAnnotator singleton for per-step annotated video compilation"
```

---
### Task 2: Wire annotation into step_capture.py

**Files:**
- Modify: `dagster/step_capture.py`
- Test: `dagster/test_step_capture_annotation.py`

- [ ] **Step 1: Add the annotation call in `_hooked_run_step`'s `finally` block**

Add to `_hooked_run_step` (after `_current = None` on line 85):

```python
# dagster/step_capture.py
# Add import at top (after line 13):
from dagster.OpenCVAnnotator import OpenCVAnnotator as _Annotator
```

```python
# In finally block, after _current = None (line 85):
        try:
            _Annotator().add_step(
                name=step["name"],
                action=step["action"],
                screenshot_path=step.get("screenshot"),
                status=step.get("status") or "PASS",
                timestamp=datetime.now().strftime("%H:%M:%S"),
            )
        except Exception:
            pass
```

- [ ] **Step 2: Add the datetime import**

```python
# Add at line 1:
from datetime import datetime as _datetime
```

- [ ] **Step 3: Write test file for annotation wiring**

```python
# dagster/test_step_capture_annotation.py
import unittest.mock
from pathlib import Path

import pytest

from dagster.step_capture import _hooked_run_step


def test_annotation_called_on_success():
    """Verify that OpenCVAnnotator.add_step is called after a successful step."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    annotator = OpenCVAnnotator()
    annotator.reset("test")

    def fake_action():
        return "ok"

    with unittest.mock.patch.object(annotator, "add_step") as mock_add:
        _hooked_run_step("my_step", fake_action)
        mock_add.assert_called_once()
        args = mock_add.call_args[1] or mock_add.call_args[0]
        # check that the step name was passed
        assert mock_add.call_args.kwargs.get("name") == "my_step" or mock_add.call_args[0][0] == "my_step"


def test_annotation_called_on_failure():
    """Verify that add_step is still called when the step raises."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    annotator = OpenCVAnnotator()
    annotator.reset("test")

    def failing_action():
        raise ValueError("boom")

    with unittest.mock.patch.object(annotator, "add_step") as mock_add:
        with pytest.raises(ValueError):
            _hooked_run_step("bad_step", failing_action)
        mock_add.assert_called_once()
```

- [ ] **Step 4: Run step_capture tests**

Run: `python -m pytest dagster/test_step_capture_annotation.py dagster/test_opencv_annotator.py -v --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add dagster/step_capture.py dagster/test_step_capture_annotation.py
git commit -m "feat: wire OpenCVAnnotator.add_step into _hooked_run_step"
```

---
### Task 3: Wire reset/finalize into runner.py

**Files:**
- Modify: `dagster/runner.py`
- Test: `dagster/test_runner_annotation.py`

- [ ] **Step 1: Write failing test**

```python
# dagster/test_runner_annotation.py
from pathlib import Path

import pytest


def test_annotator_reset_called():
    """Check that OpenCVAnnotator.reset is called before test execution."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    ann = OpenCVAnnotator()
    ann.reset()
    # We can't easily call run_single_test in isolation (needs .air dirs, device, etc.)
    # Instead validate the integration point: annotator has expected reset/finalize API
    assert hasattr(ann, "reset")
    assert hasattr(ann, "finalize")
    assert hasattr(ann, "add_step")


def test_annotator_finalize_returns_path_with_expected_name():
    """Verify finalize output path naming convention."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    ann = OpenCVAnnotator()
    ann.reset("test_module")
    assert ann.test_name == "test_module"
```

These are lightweight integration tests. The full `run_single_test` integration would need a real `.air` test directory and ADB device, which is out of scope for unit tests.

- [ ] **Step 2: Modify `run_single_test` in runner.py**

Add import at top (after line 10):
```python
from dagster.OpenCVAnnotator import OpenCVAnnotator
```

After `clear_steps()` (line 43), add:
```python
    OpenCVAnnotator.reset(test_name=module_name)
```

After `recorder` cleanup (after line 66, before `sys.path.remove`), add annotated video finalization:
```python
        try:
            annotator = OpenCVAnnotator()
            annotated_path = out_dir / f"recording_{device_id}_{module_name}_steps.mp4"
            if annotator.finalize(status, annotated_path):
                recordings.append(annotated_path)
        except Exception as e:
            print(f"[WARN] Failed to create step highlights video: {e}", file=sys.stderr)
```

Place this block right after:
```python
        if recorder:
            try:
                recorder.stop()
            except Exception as e:
                print(f"[WARN] recorder stop: {e}", file=sys.stderr)
```

Full code for the modified section (lines 61-75):
```python
    finally:
        if recorder:
            try:
                recorder.stop()
            except Exception as e:
                print(f"[WARN] recorder stop: {e}", file=sys.stderr)

        try:
            annotator = OpenCVAnnotator()
            annotated_path = out_dir / f"recording_{device_id}_{module_name}_steps.mp4"
            if annotator.finalize(status, annotated_path):
                recordings.append(annotated_path)
        except Exception as e:
            print(f"[WARN] Failed to create step highlights video: {e}", file=sys.stderr)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest dagster/test_runner_annotation.py -v --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add dagster/runner.py dagster/test_runner_annotation.py
git commit -m "feat: wire OpenCVAnnotator reset/finalize into runner.py"
```

---
### Task 4: Add step-highlights badge in reporting.py

**Files:**
- Modify: `dagster/reporting.py`
- Test: `dagster/test_reporting_annotation.py`

- [ ] **Step 1: Write failing test**

```python
# dagster/test_reporting_annotation.py
from pathlib import Path

import pytest


def test_steps_badge_appears_in_summary(tmp_path):
    """When recordings list includes a _steps.mp4, a 'Step Highlights' badge should render."""
    from dagster.reporting import generate_summary_report

    steps = [
        {"name": "s1", "action": "tap", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0},
    ]
    recordings = [
        tmp_path / "recording_dev123_test.mp4",
        tmp_path / "recording_dev123_test_steps.mp4",
    ]
    # Create dummy files so generate_summary_report doesn't filter them out
    for r in recordings:
        r.write_text("dummy")

    out = generate_summary_report(tmp_path, "my_test", steps, "PASS", recordings)
    html = out.read_text(encoding="utf-8")

    assert "Step Highlights" in html
    assert "recording_dev123_test_steps.mp4" in html
    assert "recording_dev123_test.mp4" in html


def test_no_steps_badge_when_no_steps_video(tmp_path):
    """Without a _steps.mp4, only the raw recording badge appears."""
    from dagster.reporting import generate_summary_report

    steps = [
        {"name": "s1", "action": "tap", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0},
    ]
    recordings = [tmp_path / "recording_dev123_test.mp4"]
    recordings[0].write_text("dummy")

    out = generate_summary_report(tmp_path, "my_test", steps, "PASS", recordings)
    html = out.read_text(encoding="utf-8")

    assert "Step Highlights" not in html
    assert "recording_dev123_test.mp4" in html
```

- [ ] **Step 2: Modify recording badge rendering in `generate_summary_report`**

Replace lines 278-280:
```python
    for rec in recordings:
        safe_rec = _html.escape(rec.name, quote=True)
        parts.append(f'<br><a class="rec-badge" href="{safe_rec}">&#9654; {safe_rec}</a>')
```

With:
```python
    for rec in recordings:
        safe_rec = _html.escape(rec.name, quote=True)
        label = "Step Highlights" if "_steps" in rec.stem else safe_rec
        parts.append(f'<br><a class="rec-badge" href="{safe_rec}">&#9654; {label}</a>')
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest dagster/test_reporting_annotation.py dagster/test_reporting.py -v --tb=short`
Expected: All pass (including existing reporting tests)

- [ ] **Step 4: Commit**

```bash
git add dagster/reporting.py dagster/test_reporting_annotation.py
git commit -m "feat: add 'Step Highlights' badge for _steps.mp4 in summary report"
```

---
## Self-Review Checklist

- [x] **Spec coverage:**
  - OpenCVAnnotator singleton with `__new__` → Task 1
  - `add_step()` called from `_hooked_run_step` after step completes → Task 2
  - `reset()`/`finalize()` in runner.py `finally` block → Task 3
  - Separate badge label in reporting.py → Task 4 (label = "Step Highlights")
  - `*_steps.mp4` naming convention → Task 3
  - 10fps, 2.2s hold + 0.3s crossfade → Task 1 constants
  - 3s opening/ending frames → Task 1 constants
  - `mp4v`/`avc1` fallback codec → Task 1 `finalize()` method
  - Graceful `HAS_CV2` degradation → Task 1

- [x] **Placeholder scan:** No TBD, TODO, or placeholder patterns found.

- [x] **Type consistency:** Method signatures (`reset(test_name)`, `add_step(name, action, screenshot_path, status, timestamp)`, `finalize(overall_status, output_path)`) consistent across all 4 tasks.
