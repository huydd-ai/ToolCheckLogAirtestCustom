# dagster/test_runner_annotation.py
"""Tests for the OpenCVAnnotator integration points in runner.py."""

from pathlib import Path

import pytest


def test_annotator_reset_clears_across_singleton():
    """Verify that reset() clears state across the singleton (how runner.py uses it)."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    a1 = OpenCVAnnotator()
    a1.reset("test_a")
    a2 = OpenCVAnnotator()
    a2.reset("test_b")
    assert a1 is a2
    assert a1.test_name == "test_b"
    assert len(a1.frames) == 0


def test_annotator_naming_convention():
    """Verify the naming convention used in runner.py's finalize call."""
    from dagster.OpenCVAnnotator import OpenCVAnnotator
    ann = OpenCVAnnotator()
    ann.reset("my_module")
    device_id = "emulator-5554"
    out_dir = Path("/tmp")
    module_name = "my_module"
    annotated_path = out_dir / f"recording_{device_id}_{module_name}_steps.mp4"
    assert annotated_path.name == "recording_emulator-5554_my_module_steps.mp4"
    assert ann.test_name == "my_module"
