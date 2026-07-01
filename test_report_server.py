import pytest
import report_server as rs


class _FakeProc:
    def __init__(self, rc):
        self._rc = rc

    def poll(self):
        return self._rc


def test_any_job_running_true_when_running_job_present():
    rs._jobs.clear()
    rs._jobs["j1"] = {"stem": "t", "suite": "s", "status": "running", "proc": _FakeProc(None)}
    try:
        assert rs._any_job_running() is True
    finally:
        rs._jobs.clear()


def test_any_job_running_reaps_exited_job_and_returns_false():
    """A job marked running whose process already exited must be reaped, not counted —
    otherwise a dead-but-unreaped job would wrongly keep the emulator alive."""
    rs._jobs.clear()
    rs._jobs["j1"] = {"stem": "t", "suite": "s", "status": "running", "proc": _FakeProc(0)}
    try:
        assert rs._any_job_running() is False
        assert rs._jobs["j1"]["status"] == "done"
    finally:
        rs._jobs.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
