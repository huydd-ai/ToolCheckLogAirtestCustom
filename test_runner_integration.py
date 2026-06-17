import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from dagster.runner import run_single_test
from dagster.error_capture import clear_errors, attach_error_handler
from dagster.step_capture import clear_steps, get_steps

def test_runner_promotes_pass_to_fail_on_logged_error(tmp_path):
    # Setup dummy air module
    air_dir = tmp_path / "dummy.air"
    air_dir.mkdir()
    dummy_py = air_dir / "dummy.py"
    dummy_py.write_text("""
import logging
def main():
    logger = logging.getLogger("pixon.dummy")
    logger.error("simulated logged error")
""")
    
    attach_error_handler("pixon")
    
    report_root = tmp_path / "reports"
    report_root.mkdir()
    
    # Run the test
    with patch("dagster.runner.auto_setup"), patch("dagster.runner.G"), patch("dagster.runner.importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        def mock_main():
            import logging
            logger = logging.getLogger("pixon.dummy")
            logger.error("simulated logged error")
        mock_mod.main = mock_main
        mock_import.return_value = mock_mod
        
        failed = run_single_test(air_dir, "tester", "dummy_device", report_root, "dummy_scrcpy")
        
    assert failed is True

    # Check log.txt
    out_dir = list(report_root.glob("dummy_*"))[0]
    log_txt = out_dir / "log.txt"
    assert log_txt.exists()
    content = log_txt.read_text()
    assert "Status: FAIL" in content

def test_synthetic_step_appended_for_logged_error(tmp_path):
    air_dir = tmp_path / "dummy2.air"
    air_dir.mkdir()
    (air_dir / "dummy2.py").touch()
    
    attach_error_handler("pixon")
    
    report_root = tmp_path / "reports"
    report_root.mkdir()
    
    with patch("dagster.runner.auto_setup"), patch("dagster.runner.G"), patch("dagster.runner.importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        def mock_main():
            import logging
            logger = logging.getLogger("pixon.dummy2")
            logger.error("another error")
        mock_mod.main = mock_main
        mock_import.return_value = mock_mod
        
        run_single_test(air_dir, "tester", "dummy_device", report_root, "dummy_scrcpy")
        
    out_dir = list(report_root.glob("dummy2_*"))[0]
    log_txt = out_dir / "log.txt"
    content = log_txt.read_text()
    assert "Status: FAIL" in content
    
    # Assert synthetic step exists
    steps = get_steps()
    assert any(s["action"] == "logged_error" and s["behaviour"] == "another error" for s in steps)

def test_dedup_skips_synthetic_when_step_already_captured(tmp_path):
    air_dir = tmp_path / "dummy3.air"
    air_dir.mkdir()
    (air_dir / "dummy3.py").touch()
    
    attach_error_handler("pixon")
    
    report_root = tmp_path / "reports"
    report_root.mkdir()
    
    with patch("dagster.runner.auto_setup"), patch("dagster.runner.G"), patch("dagster.runner.importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        def mock_main():
            from dagster.step_capture import _steps
            # simulate an already captured step from run_step
            _steps.append({
                "name": "some_step",
                "action": "action_failed",
                "status": "FAIL",
                "screenshot": None,
                "behaviour": "dedup error",
                "duration": 1.0,
            })
            # simulate the logger firing the same error
            import logging
            logger = logging.getLogger("pixon.dummy3")
            logger.error("dedup error")
        mock_mod.main = mock_main
        mock_import.return_value = mock_mod
        
        run_single_test(air_dir, "tester", "dummy_device", report_root, "dummy_scrcpy")
        
    steps = get_steps()
    # Should only be one step with behaviour 'dedup error'
    dedup_steps = [s for s in steps if s.get("behaviour") == "dedup error"]
    assert len(dedup_steps) == 1
    assert dedup_steps[0]["action"] == "action_failed" # Not the synthetic one
