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
