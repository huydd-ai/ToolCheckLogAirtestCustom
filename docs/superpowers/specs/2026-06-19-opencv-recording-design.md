# OpenCV Step Annotation for Test Recording

**Date:** 2026-06-19
**Status:** Approved

## Problem

Current test recording uses scrcpy for continuous MP4 capture. There is no visual
annotation — step names, PASS/FAIL status, timestamps are text-only in log.txt.
Viewers must cross-reference the video with logs to understand what happened at
each step.

## Solution

Hybrid pipeline: scrcpy continues recording full raw video (unchanged). In
parallel, at each `run_step` boundary, a per-step screenshot is captured, annotated
with OpenCV (step name, action, PASS/FAIL badge, timestamp, colored border), and
compiled into a separate "step highlights" video at test end.

## Architecture

### New file: `dagster/OpenCVAnnotator.py`

```python
class OpenCVAnnotator:
    """Captures per-step screenshots, annotates them with OpenCV,
    and compiles a highlights video at test end."""

    def add_step(name, action, screenshot_path, status, timestamp)
    def finalize() -> Path | None
```

The annotator uses a **module-level singleton** pattern (`OpenCVAnnotator.instance`),
so `step_capture.py` can call it without importing an instance from `runner.py`.
Call `OpenCVAnnotator.reset()` before each test to clear state.

**add_step()** thread-safe call from `_hooked_run_step` after each step completes.
Loads the screenshot via `cv2.imread`, draws overlays, appends to internal frame list.

**finalize()** called from `runner.py` finally block. Compiles all annotated frames
into an MP4 via `cv2.VideoWriter` with crossfade transitions.

### Integration points

| File | Change |
|------|--------|
| `step_capture.py` | After step completes in `_hooked_run_step`, call `OpenCVAnnotator.add_step(...)` with screenshot path, step name, action, status, timestamp |
| `runner.py` | Instantiate `OpenCVAnnotator` before test, call `.finalize()` in `finally`, add annotated video path to recordings list |
| `reporting.py` | Add a second badge "Step highlights" linking to the annotated MP4, alongside existing "Full recording" badge for raw scrcpy video |

### Frame annotations

| Element | Position | Style |
|---------|----------|-------|
| Step name | Top-left | White text on semi-transparent dark bar |
| Action name | Below step name | Smaller white text |
| Status badge | Top-right | Green `PASS` / Red `FAIL` pill |
| Timestamp | Bottom-right | Small gray text on dark background |
| Left border | 6px strip | Green (PASS) / Red (FAIL) |

### Video specifications

- **Format:** MP4 (H.264 codec, `cv2.VideoWriter_fourcc(*'avc1')`)
- **Frame rate:** 0.4 fps (2.5 seconds per step)
- **Transitions:** 300ms crossfade between steps via `cv2.addWeighted`
- **Resolution:** Same as source device screenshots
- **Opening frame:** Test name + date overlay on dimmed first frame (3s)
- **Ending frame:** Overall PASS/FAIL + step count summary (3s)
- **Output name:** `recording_<device>_<module>_steps.mp4`

### Error handling

- If OpenCV fails to load a screenshot frame, skip it (log warning, continue)
- If all frames fail or < 2 steps recorded, `finalize()` returns `None` (no artifacts)
- If `cv2.VideoWriter` fails to open, log warning, don't crash the test
- Missing dependencies (cv2 not importable): `OpenCVAnnotator` is a no-op
- Import-time guard: `try: import cv2; except ImportError: HAS_CV2 = False`

## File changes summary

```
dagster/
  OpenCVAnnotator.py  (NEW, ~120 lines)
  runner.py           (modified, +6 lines)
  step_capture.py     (modified, +5 lines)
  reporting.py        (modified, +3 lines)
```

Zero changes to existing scrcpy pipeline. No changes to test scripts.
