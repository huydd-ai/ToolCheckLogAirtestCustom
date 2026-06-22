from pathlib import Path

import pytest


def test_steps_badge_appears_in_summary(tmp_path):
    """When recordings list includes a _steps.mp4, a 'Step Highlights' badge should render."""
    from reporting import generate_summary_report

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
    from reporting import generate_summary_report

    steps = [
        {"name": "s1", "action": "tap", "status": "PASS", "screenshot": None, "behaviour": None, "duration": 1.0},
    ]
    recordings = [tmp_path / "recording_dev123_test.mp4"]
    recordings[0].write_text("dummy")

    out = generate_summary_report(tmp_path, "my_test", steps, "PASS", recordings)
    html = out.read_text(encoding="utf-8")

    assert "Step Highlights" not in html
    assert "recording_dev123_test.mp4" in html
